"""Core domain models shared across ingestion, retrieval, and the API.

These are pure data — no I/O, no framework coupling — so they can be
unit-tested in isolation and imported by every other package.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Where a chunk came from, precise enough for a user to verify it."""

    doc: str = Field(..., description="Human name, e.g. 'Maryland HOA Act'.")
    section: str = Field(..., description="Statute/section ref, e.g. 'RP §11B-111'.")
    breadcrumb: str = Field(
        ...,
        description="Full hierarchy path, e.g. 'MD HOA Act > 11B-111 > Meetings'.",
    )
    url: str | None = Field(None, description="Link to the public source, if any.")
    snippet: str = Field(..., description="The supporting text, verbatim.")


class Chunk(BaseModel):
    """One indexed unit of source text plus its provenance.

    `id` is a deterministic content hash so re-ingestion is a delta update
    (replace changed chunks only) rather than a full rebuild.
    """

    id: str = Field(..., description="Deterministic content hash.")
    text: str = Field(..., description="Breadcrumb header + body, as embedded.")
    citation: Citation
    jurisdiction: str = Field("MD", description="Filter key; MD-only for v1.")
    embedding: list[float] | None = Field(
        None, description="Populated at ingest; None on retrieval-side models."
    )
    embedding_model: str | None = Field(
        None, description="Model+version that produced the embedding (re-index key)."
    )


class RetrievalResult(BaseModel):
    """Ranked chunks returned by the retrieval layer."""

    chunks: list[Chunk] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)

    def top(self, k: int) -> RetrievalResult:
        """Return a new result with only the top-k chunks (already sorted)."""
        return RetrievalResult(chunks=self.chunks[:k], scores=self.scores[:k])
