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

# Load the repo-root .env (this file lives in evals/, one level down) so
# ANTHROPIC_API_KEY and MDHPP_* are picked up when running `cd evals && uv run`.
_ENV = Path(__file__).parent.parent / ".env"
if _ENV.exists():
    for _raw in _ENV.read_text().splitlines():
        _line = _raw.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        # Strip trailing inline comments ("VALUE  # note") and surrounding quotes.
        _v = _v.split("#", 1)[0].strip().strip("\"'")
        os.environ.setdefault(_k.strip(), _v)

_EVAL_SET = Path(__file__).parent / "eval_set.json"


def _judge_provider() -> str:
    """Which judge backend to use: 'ollama' (default, local, free but noisy) or
    'anthropic' (external, reliable, uses ANTHROPIC_API_KEY). Set via
    MDHPP_EVAL_JUDGE_PROVIDER. Tolerates stray whitespace/comments in .env."""
    raw = os.environ.get("MDHPP_EVAL_JUDGE_PROVIDER", "ollama")
    # Defensive: strip inline comments and whitespace so a value like
    # "anthropic  # use claude" still selects the anthropic backend.
    return raw.split("#", 1)[0].strip().lower()


_DEFAULT_ANTHROPIC_JUDGE = "claude-sonnet-4-5"


def _judge_model(provider: str, settings_model: str) -> str:
    """Resolve the judge model, tolerating stray comments/whitespace in .env."""
    default = _DEFAULT_ANTHROPIC_JUDGE if provider == "anthropic" else settings_model
    raw = os.environ.get("MDHPP_EVAL_JUDGE_MODEL", default)
    return raw.split("#", 1)[0].strip() or default


def _judge_llm() -> object:
    """Build the RAGAS judge LLM.

    Two backends, selected by MDHPP_EVAL_JUDGE_PROVIDER:
      - 'ollama' (default): local, free, but small models produce unreliable
        structured output — expect NaNs. Model via MDHPP_EVAL_JUDGE_MODEL,
        defaults to the app's llm_model.
      - 'anthropic': external Claude judge, reliable structured output and fast.
        Needs ANTHROPIC_API_KEY. Model via MDHPP_EVAL_JUDGE_MODEL, defaults to a
        current Claude model. NOTE: this makes paid API calls — never wire it
        into CI or pre-commit.
    """
    from ragas.llms import LangchainLLMWrapper

    settings = load_settings()
    provider = _judge_provider()
    model = _judge_model(provider, settings.llm_model)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "MDHPP_EVAL_JUDGE_PROVIDER=anthropic but ANTHROPIC_API_KEY is not "
                "set. Add it to the repo-root .env (no inline comment on the "
                "value) or export it."
            )
        return LangchainLLMWrapper(
            ChatAnthropic(
                model=model,
                temperature=0,
                # RAGAS's faithfulness prompt enumerates every claim in the answer
                # and returns a verdict per claim — the default output cap
                # truncates that mid-JSON (LLMDidNotFinishException -> NaN).
                max_tokens=4096,
            )
        )

    from langchain_ollama import ChatOllama

    return LangchainLLMWrapper(ChatOllama(model=model, base_url=settings.llm_host, temperature=0))


def _judge_embeddings() -> object:
    """Embeddings for answer_relevancy.

    With the Anthropic judge, use Anthropic-compatible embeddings? Anthropic has
    no embeddings API, so answer_relevancy still needs a local embed model —
    reuse the local Ollama server for embeddings regardless of judge provider.
    (faithfulness, the primary metric, doesn't need embeddings.)
    """
    from langchain_ollama import OllamaEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    settings = load_settings()
    emb_model = os.environ.get("MDHPP_EVAL_EMBED_MODEL", "nomic-embed-text")
    return LangchainEmbeddingsWrapper(OllamaEmbeddings(model=emb_model, base_url=settings.llm_host))


def run() -> None:
    from datasets import Dataset
    from ragas import evaluate

    # Metric names shifted across ragas versions: older exposes lowercase
    # instances (faithfulness), newer exposes classes (Faithfulness). Accept
    # either so a minor ragas bump doesn't break the import.
    try:
        from ragas.metrics import answer_relevancy, faithfulness
    except ImportError:  # pragma: no cover
        from ragas.metrics import (
            AnswerRelevancy,
            Faithfulness,
        )

        faithfulness = Faithfulness()
        answer_relevancy = AnswerRelevancy()

    settings = load_settings()
    # Deterministic generation for the eval: the app defaults to a small nonzero
    # temperature (fine for the product), but that makes faithfulness scores
    # jump between runs — you can't tell a regression from a dice roll. Pin to 0
    # here so the eval measures the system, not sampling noise.
    settings = settings.model_copy(update={"llm_temperature": 0.0})
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

    provider = _judge_provider()
    model = _judge_model(provider, settings.llm_model)
    print(f"\nJudge: {provider} ({model})")
    if provider == "ollama":
        print(
            "  note: a small local judge often fails RAGAS's structured-output "
            "prompts (NaNs). For reliable numbers set "
            "MDHPP_EVAL_JUDGE_PROVIDER=anthropic."
        )

    # Raise timeouts: a local CPU judge is slow and RAGAS's default (180s) times
    # out many jobs. Generous here; the Anthropic judge finishes well within it.
    from ragas.run_config import RunConfig

    run_config = RunConfig(timeout=600, max_retries=2, max_workers=4)

    # RAGAS with a small local judge is flaky: models often fail to emit the
    # exact JSON the judge prompts expect, yielding NaN for that sample. Don't
    # let one bad judge response abort the whole run; report coverage instead.
    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy],
        llm=_judge_llm(),
        embeddings=_judge_embeddings(),
        run_config=run_config,
        raise_exceptions=False,
    )
    print("\n=== RAGAS faithfulness eval ===")
    print(result)

    # Show per-sample scores and flag NaNs so a low aggregate from judge
    # failures is distinguishable from a genuinely unfaithful answer.
    try:
        df = result.to_pandas()
        import math

        print("\nper-question (NaN = judge failed to score, not a real 0):")
        for _, row in df.iterrows():
            f = row.get("faithfulness", float("nan"))
            r = row.get("answer_relevancy", float("nan"))
            fs = "NaN " if isinstance(f, float) and math.isnan(f) else f"{f:.2f}"
            rs = "NaN " if isinstance(r, float) and math.isnan(r) else f"{r:.2f}"
            print(f"  faith={fs}  relev={rs}  {str(row['user_input'])[:55]!r}")
    except Exception as exc:
        print(f"(could not render per-question table: {exc})")


if __name__ == "__main__":
    run()
