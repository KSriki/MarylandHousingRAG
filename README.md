# MDHousingPolicyPipeline

Retrieval-grounded advisory over Maryland housing, HOA, and condominium law. Ask a
plain-language question ("can my HOA stop me from installing solar panels?") and get
**guidance plus the governing policy and an exact citation** — deliberately *not* a legal
verdict.

The system points at the law rather than interpreting it: every answer is grounded in a
retrieved statute section with a forced citation, and unsupported questions get "I can't
find this in the sources" instead of a guess. That behavior is the compliance boundary,
not a UX preference.

See the [architecture docs](docs/architecture/overview.md) for the full rationale, or run
`uv run mkdocs serve` to browse them locally.

## Stack

- **Python 3.12**, `uv` workspace monorepo (single lockfile), functional-core / imperative-shell.
- **pgvector** (self-hosted, dockerized) as a single data plane: dense vectors **and**
  lexical `tsvector` full-text search **and** metadata — one SQL query, no second service.
- **BGE-M3** embeddings + **BGE-reranker-v2-m3** cross-encoder, both local (CPU), behind
  ports in `core`. No paid API required.
- **FastAPI** + SSE streaming; provider-agnostic LLM defaulting to local **Ollama**.
- **React + Vite + Tailwind + shadcn/ui** frontend (dark theme; citations are the
  signature element).
- **nginx** single-port reverse proxy terminating **TLS at the public edge**;
  **docker-compose** data plane with an init-sidecar schema.
- Quality gates: `ruff` + strict `mypy` (local + pre-commit), `pytest` with marker-gated
  unit/integration suites, GitHub Actions CI (tests).

## Layout

```
packages/
  core/        pydantic models, settings, the Embedder/Reranker/Generator ports (no I/O)
  ingestion/   parse (section-aware) -> subsection-aware chunk -> delta upsert
  retrieval/   embed + hybrid retrieve (vector + tsvector) + rerank + grounded prompt + generate
  api/         FastAPI SSE /api/ask app, grounding prompt, server-appended disclaimer
src/mdhpp/     unified `mdhpp` CLI (ingest, serve, download-models, version)
docker/        multistage Dockerfile + postgres init schema
nginx/         single-port reverse proxy (TLS at :443, :80 redirect)
scripts/       download_corpus.sh (official mgaleg statute PDFs)
corpus/        source documents (gitignored; download_corpus.sh populates statute/)
docs/          MkDocs Material site (architecture + reference)
tests/ + packages/*/tests/   unit (fast, no deps) + integration (needs dockerized pgvector)
```

## Quickstart (dev)

Prerequisites: Docker, `uv`, and **Ollama** running on the host with a model pulled
(`ollama pull llama3.2:3b`, matching `MDHPP_LLM_MODEL`).

```bash
uv sync                       # resolve + install the workspace (CPU torch)
uv run pre-commit install     # ruff + mypy on commit
uv run pytest -m unit         # fast tests, no services

# 1. Bring up the data plane and pre-warm the model cache (one-time, ~4GB to a volume)
docker compose up -d policy-db
docker compose run --rm policy-modelwarm

# 2. Get the corpus and ingest it
./scripts/download_corpus.sh   # official Maryland statute PDFs -> corpus/statute/
uv run mdhpp ingest            # parse -> chunk -> embed -> upsert (run locally vs the DB)

# 3. Bring up the full stack
#    Local TLS needs a self-signed cert (once):
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout nginx/certs/privkey.pem -out nginx/certs/fullchain.pem -subj "/CN=localhost"
docker compose up -d --build   # app served at https://localhost (accept the self-signed warning)
```

Then ask a question at `https://localhost`. Retrieval finds the governing section, the
reranker scores it, and the answer streams in with citation cards. If nothing clears the
relevance floor, you get an honest refusal instead of a guess.

`ingest` runs locally against the dockerized DB (published on `:5432`) because the API
image is intentionally scoped and doesn't carry the root CLI.

## Configuration

Settings use the `MDHPP_` env prefix (see `packages/core/src/mdhpp_core/settings.py`).
Common knobs:

| Env | Default | Purpose |
|---|---|---|
| `MDHPP_LLM_HOST` | `http://localhost:11434` | Ollama URL (compose sets `host.docker.internal`) |
| `MDHPP_LLM_MODEL` | `llama3.2:3b` | must match a model pulled on the host |
| `MDHPP_RELEVANCE_FLOOR` | `0.02` | below this rerank score, refuse rather than guess |
| `MDHPP_RETRIEVE_TOP_K` | `20` | hybrid candidates before rerank |
| `MDHPP_RERANK_TOP_K` | `5` | chunks kept after rerank |

## Build phases

- [x] **Phase 0** — repo skeleton, uv workspace, tooling, core types + settings + ports.
- [x] **Phase 1** — pgvector data plane: docker-compose, init-sidecar schema, multistage Dockerfile, volumes.
- [x] **Phase 2** — ingestion: section-aware parse, subsection-aware chunking, BGE-M3 embed, delta upsert.
- [x] **Phase 3** — retrieval + SSE API: hybrid (vector + tsvector), rerank, grounding prompt, `/api/ask`.
- [x] **Phase 4** — Vite/React/shadcn frontend consuming SSE: ask/answer, source cards, sources browser, history.
- [ ] **Phase 5** — RAGAS/DeepEval faithfulness gate (automated grounding eval in CI).

## License

MIT.
