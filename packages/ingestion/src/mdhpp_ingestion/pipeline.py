"""Ingestion pipeline orchestration (imperative shell).

Wires the pure parse/chunk stages to the shell's readers, embedder, and store:
read file -> parse sections -> chunk with breadcrumb headers -> embed -> delta
upsert. This is the seam the CLI calls; it's kept free of argument parsing so it
can also be driven from tests or a future API endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mdhpp_core import Embedder, Settings
from mdhpp_ingestion.chunk import TokenCodec, chunk_sections
from mdhpp_ingestion.parse import parse_sections
from mdhpp_ingestion.readers import doc_title_from_path, read_file
from mdhpp_ingestion.store import prune_missing, upsert_chunks


@dataclass(frozen=True)
class IngestReport:
    """Summary of what an ingest run did, for logging/CLI output."""

    doc: str
    chunks_written: int
    chunks_pruned: int


def _tiktoken_codec() -> TokenCodec:
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    return TokenCodec(encode=enc.encode, decode=enc.decode)


def ingest_file(
    path: Path,
    settings: Settings,
    embedder: Embedder,
    codec: TokenCodec | None = None,
) -> IngestReport:
    """Ingest a single source file end to end."""
    codec = codec or _tiktoken_codec()
    doc = doc_title_from_path(path)

    text = read_file(path)
    sections = parse_sections(text, doc_title=doc)
    chunks = chunk_sections(
        sections,
        doc=doc,
        codec=codec,
        chunk_size=settings.chunk_size_tokens,
        overlap=settings.chunk_overlap_tokens,
    )

    # Embed in the shell, attaching vectors + model tag to each chunk.
    vectors = embedder.embed([c.text for c in chunks])
    embedded = [
        c.model_copy(update={"embedding": v, "embedding_model": embedder.model_name})
        for c, v in zip(chunks, vectors, strict=True)
    ]

    written = upsert_chunks(settings.pg_dsn, embedded, embedder.model_name)
    pruned = prune_missing(settings.pg_dsn, doc, [c.id for c in embedded])

    return IngestReport(doc=doc, chunks_written=written, chunks_pruned=pruned)


def ingest_dir(
    corpus_dir: Path,
    settings: Settings,
    embedder: Embedder,
) -> list[IngestReport]:
    """Ingest every supported source file under a corpus directory tree."""
    codec = _tiktoken_codec()
    reports: list[IngestReport] = []
    for path in sorted(corpus_dir.rglob("*")):
        if path.suffix.lower() in {".pdf", ".html", ".htm", ".txt", ".md"}:
            reports.append(ingest_file(path, settings, embedder, codec))
    return reports
