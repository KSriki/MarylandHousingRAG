# Evaluation

Two layers, serving different purposes.

## 1. Retrieval eval (deterministic, CI-friendly)

`retrieval_eval.py` runs the real retrieval path (embed → hybrid → rerank → floor)
for every labeled question and checks:

- **`retrieve` cases** — does an expected section survive in the reranked top-k
  above the relevance floor? Reports **hit-rate** and **MRR**.
- **`refuse` cases** — does an out-of-scope question correctly decline (nothing
  clears the floor)? Reports **refusal accuracy**.

No LLM judge, deterministic, fast enough to gate CI. This is the layer that would
have caught the chunking regression and the relevance-floor drift.

```bash
make eval                                    # needs the DB up + models cached
uv run python -m evals.retrieval_eval --json # machine-readable
uv run python -m evals.retrieval_eval --hit-rate-min 0.8 --refusal-min 0.9
```

Exits non-zero if `hit_rate` or `refusal_accuracy` fall below the thresholds.

## 2. Faithfulness eval (RAGAS, LLM-judged, on-demand)

`faithfulness_eval.py` generates a real answer for each question and scores it
with RAGAS **faithfulness** (are the answer's claims grounded in the retrieved
context?) and **answer_relevancy** (does it address the question?).

The judge LLM uses the **same provider config as the app** — local Ollama by
default (`MDHPP_LLM_HOST` / `MDHPP_LLM_MODEL`), overridable to a stronger judge
via `MDHPP_EVAL_JUDGE_MODEL`. LLM-judged metrics are noisy and slow, so this is a
deliberate check, **not** a CI gate.

### Judge provider: local vs external

Small local models are **unreliable RAGAS judges** — they fail to emit the exact
JSON RAGAS's judge prompts require (you'll see `OutputParserException` and lots
of `NaN`), and they're slow enough on CPU to hit timeouts. That's a limitation of
the judge, not of your answers. Two backends, via `MDHPP_EVAL_JUDGE_PROVIDER`:

- **`ollama`** (default): local, free, but expect NaNs from a small judge. Fine
  for a rough smoke test.
- **`anthropic`**: external Claude judge — reliable structured output, fast.
  Needs `ANTHROPIC_API_KEY` in the repo-root `.env`. **Makes paid API calls.**

```bash
# reliable numbers via Claude (put ANTHROPIC_API_KEY in .env first):
MDHPP_EVAL_JUDGE_PROVIDER=anthropic make eval-faithfulness
# rough local run (free, noisy):
make eval-faithfulness
```

`answer_relevancy` still needs a local embedding model regardless of judge
(`ollama pull nomic-embed-text`); Anthropic has no embeddings API. `faithfulness`
(the primary metric) needs no embeddings.

### Cost boundary

The faithfulness eval is **never** run in CI or pre-commit — with the Anthropic
judge it would burn tokens on every push. It's a manual, deliberate command only.
CI runs the deterministic *retrieval* eval, which uses no LLM and costs nothing.


```bash
uv sync --group eval                         # installs ragas + langchain-ollama
ollama pull nomic-embed-text                 # answer_relevancy needs an embed model
make eval-faithfulness
# stronger judge:
MDHPP_EVAL_JUDGE_MODEL=llama3.1:8b make eval-faithfulness
```

## Dependency isolation

The two evals have very different dependency needs, so they're split:

- **Retrieval eval** runs in the **main project env** — it only needs the app's
  own packages (embedder, reranker, hybrid search). Run it with
  `make eval` or `uv run python -m evals.retrieval_eval` from the repo root.

- **Faithfulness eval** runs in **`evals/`'s own isolated project**
  (`evals/pyproject.toml`, its own lockfile/venv). RAGAS drags in an old,
  tightly-pinned langchain stack that conflicts with the app's dependencies if
  co-resolved; isolating it means those pins only have to be consistent with
  each other, not with torch/fastapi/etc. The eval project depends on the app
  packages by path, so it can still drive the real pipeline. Run it with
  `make eval-faithfulness` (which does `cd evals && uv run python
  faithfulness_eval.py`).

The first time you run the faithfulness eval, uv resolves and builds the
`evals/` venv separately — that's expected, and it never touches the app's
lockfile.

## The label set

`eval_set.json` — Maryland questions in two categories. Section labels are drawn
from authoritative Maryland sources (People's Law Library, statute FAQs).

**These are a starting point — refine them.** Add questions (especially real ones
users ask), correct any section labels, and grow the `refuse` set with out-of-
scope questions (CC&R-specific topics like fences/paint/parking, other
jurisdictions, non-legal questions). The eval is only as good as the labels; a
few well-chosen cases per statute area beats many redundant ones.

Why not a public dataset? General legal-QA datasets carry labels fixed to some
other jurisdiction (or generic law), so correct Maryland retrieval would score as
wrong against them, and they'd penalize correct refusals of out-of-corpus
questions. Labels must be authored against *this* corpus.
