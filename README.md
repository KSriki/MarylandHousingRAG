# MDHousingPolicyPipeline

Retrieval-grounded advisory over Maryland housing, HOA, and condominium law. Ask a
plain-language question ("can my HOA make me take down a fence?") and get **guidance
plus the governing policy and an exact citation** — deliberately *not* a legal verdict.

The system points at the law rather than interpreting it: every answer is grounded in a
retrieved source with a forced citation, and unsupported questions get "I can't find this
in the sources" instead of a guess. That behavior is the compliance boundary, not a UX
preference.

See `docs/architecture/overview.md` for the full architecture rationale.

## Stack

- **Python 3.12**, `uv` workspace monorepo (single lockfile), functional-core / imperative-shell.
- **pgvector** (self-hosted, dockerized) for vector + BM25 hybrid retrieval — no paid API.
- **BGE-M3** embeddings + **BGE-reranker-v2** cross-encoder, both local, behind a model port.
- **FastAPI** + SSE streaming; **React + Tailwind + shadcn/ui** frontend (Phase 4).
- **nginx** single-port reverse proxy; **docker-compose** data plane with an init-sidecar schema.
- Quality gates: `ruff` + strict `mypy`, `pytest` with marker-gated unit/integration suites,
  GitHub Actions CI, RAGAS/DeepEval faithfulness gate.

## Layout

```
packages/
  core/        pydantic models, settings, the embedder/reranker port (no I/O)
  ingestion/   parse -> section-aware chunk (breadcrumb headers) -> embed -> upsert
  retrieval/   hybrid retrieve + rerank + grounded prompt assembly
  api/         FastAPI SSE app, grounding prompt, disclaimer injection, rate limiting
docker/        multistage Dockerfile + postgres init schema
nginx/         single-port reverse proxy config
corpus/        source documents (gitignored; drop statute/CC&R PDFs here)
tests/         unit/ (fast, no deps) + integration/ (needs dockerized pgvector)
```

## Quickstart (dev)

```bash
uv sync                       # resolve + install the workspace
cp .env.example .env          # adjust if needed
uv run pre-commit install     # ruff + mypy on commit
uv run pytest -m unit         # fast tests, no services

docker compose up -d db       # bring up pgvector (schema auto-applied)
uv run pytest -m integration  # schema/integration tests against the DB
docker compose up             # full stack; app served on http://localhost (nginx :80)
```

Drop source documents into `corpus/` (see `corpus/sources.md`) before running
ingestion. CI (`.github/workflows/ci.yml`) runs ruff, strict mypy, and unit
tests on every push/PR, then integration tests against a pgvector service.

## Build phases

Each phase is a working, committable slice.

- [x] **Phase 0** — repo skeleton, uv workspace, tooling, core types + settings + model port.
- [x] **Phase 1** — pgvector data plane: docker-compose, init-sidecar schema, multistage Dockerfile, volumes.
- [ ] **Phase 2** — ingestion pipeline: parse, breadcrumb-header chunking, BGE-M3 embed, delta upsert.
- [ ] **Phase 3** — retrieval + SSE API: hybrid + rerank, grounding prompt, `/ask` endpoint, rate limiting.
- [ ] **Phase 4** — shadcn frontend consuming SSE, source cards, disclaimer banner.
- [ ] **Phase 5** — GitHub Actions CI, nginx single-port, RAGAS/DeepEval faithfulness gate.

## License

MIT.
