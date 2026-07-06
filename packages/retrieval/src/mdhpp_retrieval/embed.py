"""BGE-M3 embedder implementing the core Embedder port (imperative shell).

Loads the model lazily on first use so importing this module (e.g. in tests or
the CLI's --help) doesn't pull ~2GB of weights. The model name is carried on
each embedding so a later model swap forces a clean re-index rather than mixing
vector spaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from FlagEmbedding import BGEM3FlagModel


class BGEM3Embedder:
    """Local BGE-M3 dense embedder. Satisfies mdhpp_core.ports.Embedder."""

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model_name = model_name
        self._model: BGEM3FlagModel | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _ensure_model(self) -> BGEM3FlagModel:
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel

            self._model = BGEM3FlagModel(self._model_name, use_fp16=True)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        output = model.encode(texts, return_dense=True)["dense_vecs"]
        return [vec.tolist() for vec in output]
