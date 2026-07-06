"""The one abstraction worth having: the model port.

Ingestion and retrieval depend on these Protocols, not on any concrete
BGE / OpenAI / Cohere implementation. Swapping local-for-API is then a
wiring change in the imperative shell, not a code change in the core.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from mdhpp_core.models import Chunk, RetrievalResult


@runtime_checkable
class Embedder(Protocol):
    """Turns text into vectors. Same instance used at ingest and query time."""

    @property
    def model_name(self) -> str:
        """Model+version tag stored alongside embeddings for re-index safety."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, preserving order."""
        ...


@runtime_checkable
class Reranker(Protocol):
    """Cross-encoder re-scoring of candidate chunks against the query."""

    def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> RetrievalResult:
        """Return the top_k chunks re-scored for relevance to `query`."""
        ...


@runtime_checkable
class Generator(Protocol):
    """Streams a grounded answer from a prompt.

    Provider-agnostic: the concrete implementation (Ollama, an API, etc.) lives
    in the retrieval package's shell. Yields text deltas so the API can forward
    them over SSE as they're produced.
    """

    def generate(self, prompt: str) -> Iterator[str]:
        """Yield answer text chunks (deltas) for the given prompt."""
        ...
