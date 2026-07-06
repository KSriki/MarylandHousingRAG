# Decisions & alternatives

## Open issues

**Open Issue: BM25 in-Postgres vs a dedicated index**
- **Problem:** hybrid needs a lexical index. Postgres `tsvector` keeps it single-service but is a weaker BM25 than a purpose-built one.
- **Options:** (A) Postgres full-text — one service, good enough at this scale. (B) in-process `rank_bm25` over the same rows — true BM25, held in memory, fine for a small corpus. (C) add a search container — best BM25, breaks the single-data-plane goal.
- **Proposed direction:** start with (B); it's true BM25 with no extra service and the corpus fits memory.
- **Next step:** measure retrieval quality (A) vs (B) on the eval set before committing.

**Open Issue: generation model choice**
- **Problem:** local Ollama (free, private, slower/weaker) vs an API model (better instruction-following for the citation-forcing, per-token cost).
- **Options:** local-only / API-only / local-dev-API-prod behind the model port.
- **Proposed direction:** build against the port so it's a config line; default local, allow API override.
- **Next step:** eval faithfulness of a local 8B vs an API model on the citation-forcing prompt — if local holds ≥0.9, stay local.

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
