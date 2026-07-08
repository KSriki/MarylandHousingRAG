"""Token-bounded chunking with contextual breadcrumb headers (pure, no I/O).

Each section is split into chunks of at most `chunk_size` tokens with
`overlap` tokens of carry-over between consecutive chunks. Every chunk is
prefixed with its breadcrumb header (e.g. "MD HOA Act > 11B-111 > Meetings")
before embedding, so both the vector and the LLM see where the passage sits in
the document hierarchy — the single biggest retrieval-quality lever for
hierarchical legal text.

The token counter is injected (a callable str -> list[int] and its inverse) so
this module has no hard dependency on tiktoken and stays unit-testable with a
trivial fake tokenizer.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from mdhpp_core import Chunk, Citation, chunk_id
from mdhpp_ingestion.parse import Section


@dataclass(frozen=True)
class TokenCodec:
    """Encode/decode between text and token ids. Wraps tiktoken in the shell."""

    encode: Callable[[str], list[int]]
    decode: Callable[[list[int]], str]


_PAGE_ARTIFACT = re.compile(r"\n?\s*-\s*\d+\s*-\s*\n?")
# A top-level subsection marker "(a)", "(b)", ... at the start of a line (real
# statute layout). Only single lowercase letters, so it won't fire on "(1)"
# numeric items or "(iv)" romanettes. Leading whitespace before the marker is
# allowed (statute indents subsections).
_SUBSECTION = re.compile(r"(?m)^[ \t]*\(([a-z])\)\s")


def _clean_body(body: str) -> str:
    """Strip PDF page-number artifacts ("- 2 -") and collapse the vertical
    whitespace runs the extractor leaves ("\\n \\n \\n" -> "\\n\\n"), which
    otherwise dilute the text the reranker and LLM see."""
    body = _PAGE_ARTIFACT.sub("\n", body)
    # collapse runs of blank/space-only lines to a single blank line
    body = re.sub(r"(?:[ \t]*\n){2,}", "\n\n", body)
    return body.strip()


def _split_subsections(body: str) -> list[str]:
    """Split a section body into top-level subsections ((a), (b), ...).

    Keeps each operative subsection intact so it can become its own focused
    chunk, instead of a blind token window that mixes definitions with rules and
    cuts mid-sentence. If no subsection markers are found, returns the whole body
    as a single piece.
    """
    marks = [m.start() for m in _SUBSECTION.finditer(body)]
    if len(marks) < 2:
        return [body] if body.strip() else []
    pieces = []
    for i, start in enumerate(marks):
        end = marks[i + 1] if i + 1 < len(marks) else len(body)
        piece = body[start:end].strip()
        if piece:
            pieces.append(piece)
    # Any preamble before the first "(a)" (rare) is prepended to the first piece.
    if marks[0] > 0:
        pre = body[: marks[0]].strip()
        if pre and pieces:
            pieces[0] = f"{pre}\n\n{pieces[0]}"
        elif pre:
            pieces.append(pre)
    return pieces


def chunk_section(
    section: Section,
    doc: str,
    codec: TokenCodec,
    chunk_size: int,
    overlap: int,
    jurisdiction: str = "MD",
    url: str | None = None,
) -> list[Chunk]:
    """Split one section into subsection-aware, header-prefixed chunks.

    Splits at top-level subsection boundaries ((a), (b), ...) so each operative
    provision is its own focused chunk. A subsection longer than `chunk_size`
    falls back to an overlapping token-window split. The breadcrumb header is
    prepended to each chunk's embedded text; the citation snippet stores only the
    body slice.
    """
    cleaned = _clean_body(section.body)
    if not cleaned:
        return []

    header = section.breadcrumb
    pieces = _split_subsections(cleaned)

    def _emit(body_slice: str) -> Chunk:
        text = f"{header}\n\n{body_slice}"
        return Chunk(
            id=chunk_id(header, body_slice),
            text=text,
            citation=Citation(
                doc=doc,
                section=section.ref or doc,
                breadcrumb=header,
                url=url,
                snippet=body_slice,
            ),
            jurisdiction=jurisdiction,
        )

    chunks: list[Chunk] = []
    for piece in pieces:
        piece_tokens = codec.encode(piece)
        if len(piece_tokens) <= chunk_size:
            chunks.append(_emit(piece))
            continue
        # Oversized subsection: pack whole sentences up to chunk_size so we never
        # cut mid-sentence. Only a single sentence longer than chunk_size (very
        # rare in statute) is hard-split by tokens as a last resort.
        for body_slice in _pack_sentences(piece, codec, chunk_size, overlap):
            chunks.append(_emit(body_slice))

    return chunks


# Sentence boundary for the oversized-subsection fallback: a period (or ? / !)
# followed by whitespace and a capital letter or an enumerator like "(a)".
# Deliberately NOT ; or : — in statute a colon introduces an enumerated list and
# semicolons separate items WITHIN one sentence, so splitting on them would
# orphan list items from the clause that governs them.
_SENTENCE_END = re.compile(r"(?<=[.?!])\s+(?=[A-Z(])")


def _pack_sentences(text: str, codec: TokenCodec, chunk_size: int, overlap: int) -> list[str]:
    """Greedily pack whole sentences into <= chunk_size token chunks.

    Splits only on sentence-ending periods (not ; or :, which bind enumerated
    list items together in statute). Never splits a sentence unless a single
    sentence alone exceeds chunk_size, in which case it is hard-split by tokens
    as a last resort. Adds a small sentence-level overlap (the trailing sentence
    of one chunk starts the next) so context carries across boundaries.
    """
    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sent in sentences:
        n = len(codec.encode(sent))
        if n > chunk_size:
            # Flush what we have, then hard-split the oversized lone sentence.
            if current:
                chunks.append(" ".join(current))
                current, current_tokens = [], 0
            toks = codec.encode(sent)
            for i in range(0, len(toks), chunk_size):
                chunks.append(codec.decode(toks[i : i + chunk_size]).strip())
            continue
        if current_tokens + n > chunk_size and current:
            chunks.append(" ".join(current))
            # Overlap: carry the last sentence into the next chunk for continuity.
            if overlap > 0 and len(codec.encode(current[-1])) <= overlap:
                current, current_tokens = [current[-1]], len(codec.encode(current[-1]))
            else:
                current, current_tokens = [], 0
        current.append(sent)
        current_tokens += n

    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_sections(
    sections: list[Section],
    doc: str,
    codec: TokenCodec,
    chunk_size: int,
    overlap: int,
    jurisdiction: str = "MD",
    url: str | None = None,
) -> list[Chunk]:
    """Chunk every section in a document, flattening to one chunk list."""
    out: list[Chunk] = []
    for section in sections:
        out.extend(chunk_section(section, doc, codec, chunk_size, overlap, jurisdiction, url))
    return out
