"""Read source files to plain text (imperative shell — does I/O).

PDF via pypdf, HTML via trafilatura. Kept thin and separate from the pure
parse/chunk logic so the pure core never touches the filesystem.
"""

from __future__ import annotations

from pathlib import Path

import trafilatura
from pypdf import PdfReader


def read_file(path: Path) -> str:
    """Extract plain text from a source file, dispatched by extension."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix in {".html", ".htm"}:
        return _read_html(path)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported source file type: {suffix} ({path.name})")


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_html(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    extracted = trafilatura.extract(raw)
    if extracted is None:
        raise ValueError(f"Could not extract text from HTML: {path.name}")
    return extracted


def doc_title_from_path(path: Path) -> str:
    """Human doc name from the filename slug (e.g. md-hoa-act -> 'md hoa act')."""
    return path.stem.replace("-", " ").replace("_", " ")
