"""mdhpp-retrieval — hybrid retrieval + rerank + grounded prompt assembly."""

from mdhpp_retrieval.embed import BGEM3Embedder
from mdhpp_retrieval.generate import OllamaGenerator, make_generator
from mdhpp_retrieval.hybrid import hybrid_search
from mdhpp_retrieval.orchestrator import RetrievalOutcome, retrieve
from mdhpp_retrieval.prompt import build_prompt, has_grounding
from mdhpp_retrieval.rerank import BGEReranker

__all__ = [
    "BGEM3Embedder",
    "BGEReranker",
    "OllamaGenerator",
    "RetrievalOutcome",
    "build_prompt",
    "has_grounding",
    "hybrid_search",
    "make_generator",
    "retrieve",
]
