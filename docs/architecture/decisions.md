# Decisions & alternatives

## Resolved during implementation

These were open questions at design time, settled while building and running the
system against the real Maryland corpus.

**Lexical index: chose Postgres `tsvector` (was leaning rank_bm25).**
Hybrid needs a lexical signal alongside dense vectors. We shipped **(A) Postgres
full-text (`tsvector` + GIN)** rather than the originally-proposed in-process
`rank_bm25`, because it keeps the single-data-plane goal literal: one SQL query fuses
cosine similarity and `ts_rank` over the same rows, with no second process holding an
in-memory index and no application-side merge. At this corpus size the BM25-quality
difference is immaterial next to the operational simplicity. `rank_bm25` was removed
as a dependency.

**Generation model: provider-agnostic, default local Ollama.**
Built against a `Generator` port so the provider is a config line. Ships defaulting to
local Ollama (`llama3.2:3b` by default — must match a model pulled on the host). An API
model remains a drop-in override behind the port. `MDHPP_LLM_HOST`/`MDHPP_LLM_MODEL`
configure it; in Docker the host Ollama is reached via `host.docker.internal`.

**Embedder lives in `retrieval`, not `ingestion`.**
The API embeds the *query* at request time, so the embedder is a shared dependency of
both ingestion (document embedding) and the API (query embedding). It lives in
`retrieval`, which both reach. This means the API image legitimately carries torch —
so the CPU-torch pin (below) is what keeps that image lean, not dependency scoping.

**CPU-only torch.**
`retrieval` pulls torch via FlagEmbedding; the default Linux build declares ~1.5GB of
CUDA/nvidia libraries we have no GPU for. torch is pinned to PyTorch's CPU index so the
venv (and the runtime image) stay ~200MB instead of ~2GB. `transformers` is pinned
`<5` because FlagEmbedding 1.4's reranker uses the pre-5.x tokenizer API.

**Chunking: structure-aware, not a blind token window.**
Statute is header-delimited (`(a)/(b)/(c)`). Sections are split at subsection
boundaries so each operative provision is a focused chunk, with a sentence-safe
fallback (never splitting on `;`/`:`, which bind enumerated list items) for any
subsection exceeding the token budget. PDF page-number artifacts (`- 2 -`) and the
extractor's whitespace noise are stripped. This was the fix for a class of failures
where the operative rule was buried in a definitions-heavy blob and scored near-zero at
rerank.

**Reranker scores full chunk text at `max_length=1024`.**
The cross-encoder scores the query against the full chunk `text` (not the truncated
citation snippet), and `max_length` is raised from FlagEmbedding's 512-token default so
the whole chunk is in view rather than just its leading tokens.

**Relevance floor tuned to the reranker's distribution (0.02).**
The BGE cross-encoder scores a correct-but-lexically-distant legal match (colloquial
question vs formal statute) around 0.05, far below a clean-prose intuition. The floor
below which the system refuses rather than guesses is set to 0.02 —
correct matches pass, off-topic noise (which scores ~0.0001) still refuses.
Env-tunable via `MDHPP_RELEVANCE_FLOOR`; it is a real safety control, not just a knob.

**TLS at the public edge only.**
nginx terminates TLS on :443 (with a :80 redirect); internal docker-network hops
(nginx→api, api→db/ollama) stay HTTP. On a single-node deploy the docker network is the
trust boundary; TLS is spent where traffic crosses the real network.

---

## Alternatives considered

- **Qdrant instead of pgvector:** stronger payload filtering and native hybrid, but a second stateful service. Rejected for v1 to keep a single data plane (finradar-style); the corpus is well within pgvector's range (KB §1.5.1). Revisit if filtering needs outgrow Postgres.
- **Pure vector retrieval (no BM25):** rejected — legal text is exact-token-heavy (section numbers, defined terms); pure dense blurs precisely the citations users need (the r/LangChain thread's core lesson, and KB's "hybrid beats pure-vector when a concept meets a hard constraint"). Note the reference implementation (`launch-rag`) uses pure vector similarity; this is a deliberate upgrade for the legal-citation domain, not an oversight.
- **Supabase-hosted pgvector (as in the reference `launch-rag`):** rejected for v1 — it's a paid managed service and pulls embeddings/generation to OpenAI APIs, both of which violate the self-hosted / no-mandatory-paid-API constraint. Self-hosted dockerized pgvector gives the same Postgres+pgvector primitives with no external dependency. Supabase remains a reasonable path if this ever needs managed auth + RLS (its `rag-with-permissions` model would map onto the v2 per-user-CC&R feature).
- **Skipping reranking:** rejected — it's the single biggest quality lever per the interview-prep RAG doc; cutting it to save latency trades away the pillar we're optimizing for.
- **Agentic RAG from day one:** rejected — KB §1.4 "don't skip rungs." Classic one-shot RAG first; add agency only where eval shows multi-hop failures.
- **Letting the model give a verdict:** rejected on legal grounds — it's the compliance boundary, not a UX preference.

---

### Appendix: section-to-KB cross-reference

| Doc section | KB framework |
|---|---|
| Background, SLOs | §0.5 Five Pillars (Reliability/faithfulness) |
| Architecture · A | §0.7 Ladder of Complexity (Rung 2) |
| Architecture · B | §0.8 Functional Core, Imperative Shell |
| Architecture · C | §1, §1A structural + vertical-slice; §1A.11 (not hexagonal) |
| Architecture · D | §Pattern 3 RAG; §6.2 ACL; §7.2 Cache-Aside; §4 API Gateway |
| Dependencies | §2A scale-up-first; §1.5.1 pgvector fit |
| Monitoring | §0.9.5 decision-path observability |
| Security | §5A (no-auth recorded, rate limiting, secrets, injection) |
| Alternatives | §0.7, §1.4, §1.5 (rejected rung/DB/pattern) |
