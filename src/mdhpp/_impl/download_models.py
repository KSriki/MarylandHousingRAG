"""Implementation of `mdhpp download-models`.

Pre-warms the model cache by downloading the embedder and reranker weights into
the HuggingFace cache (a persistent volume in the deployed stack). Run once per
environment after deploy so the first real /api/ask request doesn't pay the
~4GB download cost mid-request.
"""

from __future__ import annotations


def run() -> None:
    from mdhpp_core import load_settings
    from mdhpp_retrieval.embed import BGEM3Embedder
    from mdhpp_retrieval.rerank import BGEReranker

    settings = load_settings()

    print(f"Downloading embedder: {settings.embedding_model} ...")
    embedder = BGEM3Embedder(settings.embedding_model)
    # A tiny embed call forces the lazy model load, pulling weights to the cache.
    embedder.embed(["warm up"])
    print("  embedder ready.")

    print(f"Downloading reranker: {settings.reranker_model} ...")
    reranker = BGEReranker(settings.reranker_model)
    # A trivial rerank forces the reranker's weights to download too.
    from mdhpp_core import Chunk, Citation

    warm = Chunk(
        id="warm",
        text="warm up",
        citation=Citation(
            doc="warm",
            section="warm",
            breadcrumb="warm",
            url=None,
            snippet="warm up",
        ),
    )
    reranker.rerank("warm up", [warm], top_k=1)
    print("  reranker ready.")

    print("Model cache warmed. Weights are cached in the HF cache volume.")
