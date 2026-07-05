"""Implementation of `mdhpp ingest`.

Dispatches to the mdhpp_ingestion pipeline. Kept out of cli.py so the Typer
layer stays import-light and dispatch-only.
"""

from __future__ import annotations

from pathlib import Path


def run(source: Path | None, corpus: Path) -> None:
    from mdhpp_core import load_settings
    from mdhpp_ingestion.embed import BGEM3Embedder
    from mdhpp_ingestion.pipeline import ingest_dir, ingest_file

    settings = load_settings()
    embedder = BGEM3Embedder(settings.embedding_model)

    if source is not None:
        report = ingest_file(source, settings, embedder)
        print(f"{report.doc}: wrote {report.chunks_written} chunks, pruned {report.chunks_pruned}")
        return

    reports = ingest_dir(corpus, settings, embedder)
    if not reports:
        print(f"No source files found under {corpus}/")
        return
    total_written = sum(r.chunks_written for r in reports)
    total_pruned = sum(r.chunks_pruned for r in reports)
    for r in reports:
        print(f"  {r.doc}: wrote {r.chunks_written}, pruned {r.chunks_pruned}")
    print(
        f"Done: {total_written} chunks written, {total_pruned} pruned, "
        f"across {len(reports)} document(s)."
    )
