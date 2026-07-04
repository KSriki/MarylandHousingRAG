"""Deterministic chunk identity.

A chunk's id is a hash of (breadcrumb + text). Re-running ingestion on an
amended statute produces the same id for unchanged chunks and a new id for
changed ones, so the upsert is a delta — not a full-index rebuild.
"""

from __future__ import annotations

import hashlib


def chunk_id(breadcrumb: str, text: str) -> str:
    """Stable id for a chunk, independent of ingest run or machine."""
    h = hashlib.sha256()
    h.update(breadcrumb.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:32]
