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
from mdhpp_retrieval.jurisdiction import detect_other_state
from mdhpp_retrieval.prompt import build_prompt, has_grounding


@dataclass(frozen=True)
class RetrievalOutcome:
    """Result of the retrieval stage handed to the API.

    `grounded` is False when the query is out of jurisdiction or nothing cleared
    the relevance floor; the API then returns a refusal and does not call the
    generator. `refusal_reason` distinguishes the cases so the API can tailor the
    message: "jurisdiction" (another state named) or "not_found" (no grounding).
    """

    grounded: bool
    prompt: str
    chunks: list[Chunk]
    refusal_reason: str | None = None


def retrieve(
    question: str,
    settings: Settings,
    embedder: Embedder,
    reranker: Reranker,
    jurisdiction: str = "MD",
) -> RetrievalOutcome:
    """Run the full retrieval path and return a prompt (or a refusal signal)."""
    # Jurisdiction guard: if the question names another US state, decline before
    # retrieval — the corpus is Maryland only, and a topical HOA question about
    # another state can otherwise slip past the relevance floor.
    other = detect_other_state(question)
    if other is not None:
        return RetrievalOutcome(grounded=False, prompt="", chunks=[], refusal_reason="jurisdiction")

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
        return RetrievalOutcome(grounded=False, prompt="", chunks=[], refusal_reason="not_found")

    prompt = build_prompt(question, reranked.chunks)
    return RetrievalOutcome(grounded=True, prompt=prompt, chunks=reranked.chunks)
