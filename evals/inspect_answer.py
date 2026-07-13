"""Inspect a generated answer against its retrieved context.

Faithfulness scores tell you an answer contains unsupported claims, but not
WHICH ones. This prints the retrieved passages and the generated answer side by
side so you can see what the model asserted that the statute doesn't say.

Run (from evals/, in the isolated eval project):
    uv run python inspect_answer.py                 # the known-bad cases
    uv run python inspect_answer.py "your question here"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mdhpp_core import load_settings
from mdhpp_retrieval import make_generator, retrieve
from mdhpp_retrieval.embed import BGEM3Embedder
from mdhpp_retrieval.rerank import BGEReranker

# Load repo-root .env (same loader as faithfulness_eval).
_ENV = Path(__file__).parent.parent / ".env"
if _ENV.exists():
    for _raw in _ENV.read_text().splitlines():
        _line = _raw.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _v = _v.split("#", 1)[0].strip().strip("\"'")
        os.environ.setdefault(_k.strip(), _v)

# The lowest-faithfulness cases from the RAGAS run.
_DEFAULT_QUESTIONS = [
    "Can my HOA prohibit an electric vehicle charging station?",  # faith=0.00
    "How much advance notice do I get before the HOA adopts its annual budget?",  # 0.33
    "What is the most the HOA can charge as a late fee?",  # 0.50
]


def inspect(question: str) -> None:
    settings = load_settings()
    embedder = BGEM3Embedder(settings.embedding_model)
    reranker = BGEReranker(settings.reranker_model)
    generator = make_generator(settings)

    outcome = retrieve(question, settings, embedder, reranker)
    print("=" * 78)
    print(f"QUESTION: {question}")
    print("=" * 78)

    if not outcome.grounded:
        print("\n(refused — nothing cleared the relevance floor)\n")
        return

    print(f"\n--- RETRIEVED CONTEXT ({len(outcome.chunks)} chunks) ---")
    for i, c in enumerate(outcome.chunks, start=1):
        print(f"\n[passage {i}] {c.citation.section}")
        print(c.text.strip())

    answer = "".join(generator.generate(outcome.prompt))
    print("\n--- GENERATED ANSWER ---")
    print(answer.strip())
    print(
        "\n--- CHECK: does every claim above appear in the passages? "
        "Anything extra is an ungrounded claim (what RAGAS penalizes). ---\n"
    )


def main() -> None:
    questions = sys.argv[1:] or _DEFAULT_QUESTIONS
    for q in questions:
        inspect(q)


if __name__ == "__main__":
    main()
