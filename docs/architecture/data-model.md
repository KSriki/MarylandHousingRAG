# Data model & dependencies

## Dependencies / infrastructure

- **Language:** Python 3.12 — near-irreversible; matches your stack, ecosystem for RAG (langchain, sentence-transformers) is Python-first.
- **Runtime / hosting:** single host, docker-compose (KB §2A — scale *up* before out; a modern box handles this workload with room to spare). No k8s.
- **Persistent storage:** **PostgreSQL 16 + pgvector (HNSW index)** — high-penalty choice, argued: one container serves both the vector store *and* the relational metadata/BM25-adjacent needs, keeping the data plane to a single service (the finradar simplification). pgvector at this corpus size (statute + docs, not millions of chunks) is comfortably within its sweet spot per KB §1.5.1. BM25 via Postgres full-text (`tsvector`) or a lightweight in-process index over the same rows — no separate search service.
- **Key third-party packages:** `sentence-transformers` / `FlagEmbedding` (BGE-M3 embed + BGE-reranker), `fastapi` + `sse-starlette`, `pydantic` / `pydantic-settings`, `psycopg` + `pgvector`, `pypdf` / `trafilatura` (PDF + HTML parsing per the research-library guide), `langgraph` (thin, leaves the agentic seam open).
- **Low-stakes / easily-swapped deps:** the generation LLM (local Ollama vs API) is one config line behind the model port — deliberately not over-specified.

---
