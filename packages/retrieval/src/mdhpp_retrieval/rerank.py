"""BGE cross-encoder reranker implementing the core Reranker port (shell).

Reranking re-scores the hybrid shortlist with a cross-encoder that reads the
query and each chunk together (unlike the bi-encoder embeddings, which score
them independently). It's the single biggest retrieval-quality lever. Weights
load lazily so importing this module is cheap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mdhpp_core import Chunk, RetrievalResult

if TYPE_CHECKING:
    from FlagEmbedding import FlagReranker


class BGEReranker:
    """Local BGE cross-encoder. Satisfies mdhpp_core.ports.Reranker."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self._model_name = model_name
        self._model: FlagReranker | None = None

    def _ensure_model(self) -> FlagReranker:
        if self._model is None:
            from FlagEmbedding import FlagReranker

            self._model = FlagReranker(self._model_name, use_fp16=True)
        return self._model

    def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> RetrievalResult:
        if not chunks:
            return RetrievalResult(chunks=[], scores=[])

        model = self._ensure_model()
        # Rerank against the full chunk text, not the truncated citation snippet.
        # The snippet is just a short preview (often definitional boilerplate like
        # "In this section the following words..."), which gives the cross-encoder
        # nothing to match against and collapses all scores toward zero.
        pairs = [[query, c.text] for c in chunks]
        raw = model.compute_score(pairs, normalize=True)
        scores = [float(s) for s in raw] if isinstance(raw, list) else [float(raw)]

        ranked = sorted(zip(chunks, scores, strict=True), key=lambda p: p[1], reverse=True)
        top = ranked[:top_k]
        return RetrievalResult(
            chunks=[c for c, _ in top],
            scores=[s for _, s in top],
        )
