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

from collections.abc import Callable
from dataclasses import dataclass

from mdhpp_core import Chunk, Citation, chunk_id
from mdhpp_ingestion.parse import Section


@dataclass(frozen=True)
class TokenCodec:
    """Encode/decode between text and token ids. Wraps tiktoken in the shell."""

    encode: Callable[[str], list[int]]
    decode: Callable[[list[int]], str]


def chunk_section(
    section: Section,
    doc: str,
    codec: TokenCodec,
    chunk_size: int,
    overlap: int,
    jurisdiction: str = "MD",
    url: str | None = None,
) -> list[Chunk]:
    """Split one section into overlapping, header-prefixed chunks.

    The breadcrumb header is prepended to each chunk's embedded text but the
    citation snippet stores only the body slice, so the snippet shown to a user
    is the actual statute text, not the header.
    """
    if not section.body.strip():
        return []

    header = section.breadcrumb
    body_tokens = codec.encode(section.body)
    step = max(1, chunk_size - overlap)

    chunks: list[Chunk] = []
    for start in range(0, len(body_tokens), step):
        window = body_tokens[start : start + chunk_size]
        if not window:
            break
        body_slice = codec.decode(window).strip()
        if not body_slice:
            continue

        text = f"{header}\n\n{body_slice}"
        citation = Citation(
            doc=doc,
            section=section.ref or doc,
            breadcrumb=header,
            url=url,
            snippet=body_slice,
        )
        chunks.append(
            Chunk(
                id=chunk_id(header, body_slice),
                text=text,
                citation=citation,
                jurisdiction=jurisdiction,
            )
        )
        # Stop once this window reached the end (avoid a trailing dup chunk).
        if start + chunk_size >= len(body_tokens):
            break

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
