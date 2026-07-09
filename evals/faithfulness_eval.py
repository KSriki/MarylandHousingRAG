"""RAGAS faithfulness eval — LLM-judged, on-demand (not a CI gate).

Runs the full pipeline (retrieve -> generate) for each `retrieve` case, then
scores the generated answer with RAGAS:
  - faithfulness: is every claim in the answer supported by the retrieved context?
  - answer_relevancy: does the answer actually address the question?

The judge LLM and embeddings use the SAME provider config as the app, so this
runs against local Ollama by default and an external provider when configured
(MDHPP_EVAL_JUDGE_MODEL / MDHPP_LLM_HOST). LLM-judged metrics are noisy and
slow, so this is meant to be run deliberately, not on every CI push.

Requires the `eval` dependency group:  uv sync --group eval
Run:  uv run python -m evals.faithfulness_eval
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mdhpp_core import load_settings
from mdhpp_retrieval import make_generator, retrieve
from mdhpp_retrieval.embed import BGEM3Embedder
from mdhpp_retrieval.rerank import BGEReranker

_EVAL_SET = Path(__file__).parent / "eval_set.json"


def _judge_llm() -> object:
    """Build the RAGAS judge LLM from app-aligned config.

    Uses langchain-ollama by default (matching the app's local Ollama), pointed
    at MDHPP_LLM_HOST. Set MDHPP_EVAL_JUDGE_MODEL to override the judge model
    (a stronger model gives more reliable judgments than a small local one).
    """
    from langchain_ollama import ChatOllama
    from ragas.llms import LangchainLLMWrapper

    settings = load_settings()
    host = settings.llm_host
    model = os.environ.get("MDHPP_EVAL_JUDGE_MODEL", settings.llm_model)
    return LangchainLLMWrapper(ChatOllama(model=model, base_url=host, temperature=0))


def _judge_embeddings() -> object:
    from langchain_ollama import OllamaEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    settings = load_settings()
    # answer_relevancy needs an embedding model; reuse the local Ollama server.
    emb_model = os.environ.get("MDHPP_EVAL_EMBED_MODEL", "nomic-embed-text")
    return LangchainEmbeddingsWrapper(OllamaEmbeddings(model=emb_model, base_url=settings.llm_host))


def run() -> None:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, faithfulness

    settings = load_settings()
    embedder = BGEM3Embedder(settings.embedding_model)
    reranker = BGEReranker(settings.reranker_model)
    generator = make_generator(settings)

    data = json.loads(_EVAL_SET.read_text())
    rows: dict[str, list[object]] = {"question": [], "answer": [], "contexts": []}

    for case in data.get("retrieve", []):
        q = case["question"]
        outcome = retrieve(q, settings, embedder, reranker)
        if not outcome.grounded:
            print(f"  (skip, refused) {q!r}")
            continue
        answer = "".join(generator.generate(outcome.prompt))
        rows["question"].append(q)
        rows["answer"].append(answer)
        rows["contexts"].append([c.text for c in outcome.chunks])
        print(f"  answered {q!r}")

    if not rows["question"]:
        print("No grounded answers to evaluate.")
        return

    ds = Dataset.from_dict(rows)
    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy],
        llm=_judge_llm(),
        embeddings=_judge_embeddings(),
    )
    print("\n=== RAGAS faithfulness eval ===")
    print(result)


if __name__ == "__main__":
    run()
