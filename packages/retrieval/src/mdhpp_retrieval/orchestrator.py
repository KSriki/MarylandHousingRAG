"""Retrieval orchestration (shell): the seam the API calls.

Ties the stages together: embed the query, hybrid-retrieve, rerank, check the
relevance floor, and assemble the grounded prompt. Returns either a prompt ready
for generation, or a signal that nothing cleared the floor (so the API can
return the "can't find it" refusal instead of generating).
"""

from __future__ import annotations

from dataclasses import dataclass

from mdhpp_core import Chunk, Embedder, Reranker, Settings
from mdhpp_retrieval.hybrid import hybrid_search
from mdhpp_retrieval.prompt import build_prompt, has_grounding


@dataclass(frozen=True)
class RetrievalOutcome:
    """Result of the retrieval stage handed to the API.

    `grounded` is False when nothing cleared the relevance floor; the API then
    returns the refusal and does not call the generator.
    """

    grounded: bool
    prompt: str
    chunks: list[Chunk]


def retrieve(
    question: str,
    settings: Settings,
    embedder: Embedder,
    reranker: Reranker,
    jurisdiction: str = "MD",
) -> RetrievalOutcome:
    """Run the full retrieval path and return a prompt (or a refusal signal)."""
    (query_vec,) = embedder.embed([question])

    hits = hybrid_search(
        dsn=settings.pg_dsn,
        query_text=question,
        query_embedding=query_vec,
        top_k=settings.retrieve_top_k,
        jurisdiction=jurisdiction,
    )

    reranked = reranker.rerank(question, hits.chunks, settings.rerank_top_k)

    if not has_grounding(reranked.chunks, reranked.scores, settings.relevance_floor):
        return RetrievalOutcome(grounded=False, prompt="", chunks=[])

    prompt = build_prompt(question, reranked.chunks)
    return RetrievalOutcome(grounded=True, prompt=prompt, chunks=reranked.chunks)
