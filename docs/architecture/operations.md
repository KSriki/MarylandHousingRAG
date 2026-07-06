# Operations

## Service level objectives (SLOs)

- **Availability:** 99% monthly (single-host personal/small tool; no HA requirement).
- **Latency:** p50 ≤ 2.5 s to first streamed token, p95 ≤ 6 s end-to-end (hybrid + rerank + local generation is inherently slower than a bare call — this is the Performance we traded for faithfulness).
- **Scale / throughput:** designed for low tens of concurrent users; 10× headroom before pgvector or the local model runtime needs revisiting.
- **Quality SLO (the one that matters):** faithfulness ≥ 0.9 and answer-relevance ≥ 0.85 on the eval set (RAGAS/DeepEval) before any release. This is how "reliability" from Background is proven.

---

## Monitoring / alerting

**These events page you (or hit the dashboard):**
- Faithfulness eval score drops below 0.85 on the regression set in CI — blocks release.
- p95 first-token latency ≥ 10 s sustained 5 min.
- Model runtime (Ollama/embedder container) unhealthy or OOM.
- Retrieval returning empty/below-floor for > 20% of queries in a window (corpus or index problem).

Observability captures the **decision path** (KB §0.9.5): every query logs its retrieved chunk IDs, rerank scores, and which citations made it into the answer — so a bad answer is debuggable to the exact retrieval step. structlog with a contextvar `trace_id` per request (the AgentRadar pattern).

---

## Logging

**Events logged:** per-query retrieval trace (chunk IDs, rerank scores, chosen citations); ingestion runs (docs processed, chunks upserted/replaced, embedding model version tag — non-negotiable per the RAG doc, since swapping embedders means re-embedding); generation failures and timeouts; rate-limit rejections.
**Kept out of logs:** any API keys/tokens, and long-term storage of user IP linked to question content.

---

## Constraints

- **Self-hosted, no mandatory paid API:** forces local dockerized embed + rerank (BGE-M3 / BGE-reranker) and makes the generation model swappable to local Ollama. Shapes the model-port abstraction.
- **Docker volumes over copy-in:** pgvector data, the HF/model cache, and downloaded weights all live in **named volumes**, not baked into images — keeps image builds fast and models out of layers.
- **Single nginx port:** everything behind `:80`, `/api` reverse-proxied, SSE buffering disabled (`proxy_buffering off`) so streaming actually streams.

---

## Timeline

- **Milestone 1:** React/shadcn UI + FastAPI SSE endpoint returning **hardcoded** answer+citation. Proves the streaming UX and the disclaimer flow end-to-end before any retrieval exists (Lynch: ship the UI with dummy data first to catch requirement misreads early).
- **Milestone 2:** ingestion pipeline on a small real corpus (the MD HOA Act) → pgvector; wire hybrid retrieve + rerank into the live path. First real grounded answers.
- **Milestone 3:** grounding/guardrail prompt hardened; "can't find it" path enforced; RAGAS/DeepEval eval set + CI gate on faithfulness. Cache-aside + rate limiting in.
- **Milestone 4:** full corpus (statute + selected county code + sample CC&Rs), docker-compose production profile, nginx, GitHub Actions green (ruff, mypy, marker-gated pytest), deploy.

---
