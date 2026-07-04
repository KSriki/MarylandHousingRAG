# Software Architecture Design Doc — MDHousingPolicyPipeline

## Title

**MDHousingPolicyPipeline** (short name: **PolicyPipeline**)

> A retrieval-grounded advisory system over Maryland housing, HOA, and condominium law. Given a homeowner's plain-language question ("can my HOA make me take down a fence?"), it returns **guidance plus the governing policy and citation** — deliberately *not* a legal answer. The "pipeline" name reflects the two-pipeline RAG shape and the reality that statute changes slowly; there is no fast-moving "radar" signal to scan for.

---

## Metadata

- **Author:** 〈Your Name〉 (〈email〉)
- **Status:** Draft
- **Created:** 2026-07-03
- **Last updated:** 2026-07-03
- **Authoritative URL:** `github.com/〈you〉/MDHousingPolicyPipeline`
- **Reviewers:** 〈self / peer reviewer〉

---

## Objective

Give Maryland homeowners and HOA members plain-language *guidance* on what the law and their governing documents say about a proposed action — surfacing the relevant policy and an exact citation rather than issuing a legal ruling.

---

## Background

Homeowners routinely face questions with a legal answer buried in three overlapping places: **Maryland statute** (the Homeowners Association Act and Maryland Condominium Act in the Real Property Article), **their own HOA's recorded covenants (CC&Rs) and bylaws**, and **county/municipal code**. The information exists and is public, but it is unindexed for a layperson: you cannot search "can they fine me for a fence" and land on the controlling section. The current alternatives are paying a lawyer for a question that is often answerable from the text, or guessing.

The failure this project addresses is an **information-retrieval and trust problem**, not a generation problem. A generic chatbot will confidently *answer* — "no, they can't fine you" — which is exactly the wrong behavior: it manufactures legal advice, it can hallucinate a nonexistent rule, and it strips the citation the user actually needs to act. The hard part is retrieving the *right* passage (legal text is dense with exact tokens — `§11B-111`, "architectural review committee," specific dollar caps) and then **forcing the model to ground every statement in a retrieved citation** and to frame output as informational.

**Pillar this optimizes for (KB §0.5): Reliability**, specifically *faithfulness* — the answer must be grounded in retrieved source or the system must say it doesn't know. It knowingly trades **Performance** (hybrid retrieval + reranking + citation-forcing is slower than a bare LLM call) and accepts modest **Cost** for eval tooling. It is emphatically not optimizing for scale — this is a low-QPS advisory tool.

---

## Related documents

- **Pattern reference:** `software-architecture-patterns-knowledge-base.md`
- **RAG stage reference:** `cloud-ai-platforms-comparison-knowledge-base.md` §Pattern 3 (RAG two-pipeline shape); `puffypenguin_interview_prep2.pdf` §7 (full RAG pipeline).
- **Structural prior art:** AgentRadar / finradar repos — uv workspace monorepo, single nginx port, docker-compose data plane, marker-gated pytest.
- **Retrieval technique source:** r/LangChain thread on language-specific RAG — the transferable levers are hybrid (BM25 + dense), contextual chunk headers, and reranking.
- **Reference implementation (skeleton):** Sean Chen, "RAG AI Agent Design & Launch in 35 Min" (`youtube.com/watch?v=ZREt9MAozho`), code at `github.com/ShenSeanChen/launch-rag`. A FastAPI + pgvector (via Supabase) RAG backend with citation-tracked answers, Dockerized to Cloud Run. This project borrows its shape — FastAPI, pgvector, citation-in-response, `/seed` + `/answer` endpoints, Docker — and deliberately diverges on four points: (1) **self-hosted dockerized pgvector** vs Supabase-hosted; (2) **local BGE-M3 embeddings** vs OpenAI `text-embedding-3-large`; (3) **hybrid retrieval + rerank** vs pure vector similarity; (4) **guidance-not-verdict + relevance-floor refusal + SSE streaming** vs always-answer JSON. Note the reference, despite the "agent" name, is **classic one-shot RAG** (retrieve-then-generate, no decision loop) — which matches this design's v1 rung (see Architecture · A and the Non-goal on agentic reasoning).

---

## Goals

- A homeowner gets **guidance + the governing rule + an exact citation** for a housing/HOA question, in plain language.
- Every substantive claim in an answer is **traceable to a retrieved chunk**; unsupported questions get "I can't find this in the sources" rather than a guess.
- Output is consistently framed as **informational, not legal advice**, with a standing disclaimer.
- The corpus is **re-ingestible** — when a statute is amended, re-running ingestion updates the index without a full rebuild.
- Runs entirely **self-hosted / dockerized** with no per-token API dependency for embeddings or reranking.

---

## Non-goals

- **Giving a legal ruling or a "yes/no you're allowed" verdict** — out of scope by design; that's practicing law and creates liability. The system points at policy.
- **Real-time monitoring for law changes** — out of scope; statute changes slowly, ingestion is run on demand. (This is why it's not "radar.")
- **Case law / court opinions** — v1 is statute + governing docs + county code only; case law retrieval is a v2 corpus expansion.
- **Multi-state coverage** — Maryland only for v1; the `jurisdiction` metadata field leaves the seam open.
- **User accounts uploading their own private CC&Rs** — v1 ships with a curated public corpus; per-user document ingestion is v2 (adds a whole auth/tenancy surface).
- **Agentic multi-hop reasoning** — v1 is classic one-shot RAG. Per KB §1.4, don't skip rungs; add agency only where eval shows one-shot retrieval failing.

---

## Glossary

- **CC&Rs:** Covenants, Conditions & Restrictions — the recorded rulebook a specific HOA enforces. Sits *below* statute; statute overrides a conflicting covenant.
- **Contextual chunk header:** a breadcrumb (e.g. `[MD HOA Act › §11B-111 › Meetings — Notice]`) prepended to each chunk before embedding, so both retrieval and the LLM see where a passage sits in the document hierarchy.
- **Hybrid retrieval:** BM25 (lexical/keyword) + dense (semantic vector) run together and fused. BM25 catches exact section numbers and defined terms; dense catches paraphrase.
- **Reranking:** a cross-encoder (BGE-reranker) re-scores the top-k candidates from hybrid retrieval; the single biggest quality lever per the interview-prep RAG doc.
- **Faithfulness:** the eval metric for "is the answer grounded in the retrieved context, or did the model make it up?" (KB §0.9.5 / RAG triad).
- **SSE:** Server-Sent Events — one-way streaming from FastAPI to the browser, used to stream tokens and citations as they're produced.

---

## Scenarios

**Scenario: answerable question with a clean citation**
1. User types "Can my HOA stop me from installing solar panels?"
2. Query is embedded (BGE-M3) and run through BM25 in parallel; hybrid fusion returns top-20 candidate chunks filtered to `jurisdiction=MD`.
3. BGE-reranker re-scores; top-5 pass to the LLM as XML-tagged context, each carrying its breadcrumb header and citation.
4. LLM streams (SSE) a plain-language summary of the rule, notes Maryland limits an HOA's ability to prohibit solar, and cites the controlling Real Property section — framed as "here's what the law says," not "you're allowed."
5. UI renders the streamed answer with the citation as a clickable source card, plus the standing "informational, not legal advice" banner.

**Scenario: question the corpus can't support**
1. User asks about a niche tax-lien interaction not in the ingested corpus.
2. Hybrid retrieval + rerank return only low-score chunks (below the relevance floor).
3. The generation prompt's grounding rule triggers: the model responds that it can't find governing policy for this in its sources and suggests consulting an attorney or the specific county office — it does **not** improvise a rule.

**Scenario: re-ingestion after an amendment**
1. Maintainer drops an updated statute PDF into the source folder and runs `uv run ingest`.
2. Ingestion parses → section-aware chunks with fresh breadcrumb headers → embeds → upserts into pgvector by stable content hash, replacing changed chunks only (delta update, not full rebuild).

---

## Architecture overview

### A. Complexity rung (KB §0.7)

**Chosen rung: Rung 2 — modular monolith**, deployed as a small set of docker-compose services (backend, db, frontend, nginx) but with the *application* code as one deployable split into internal packages (`ingestion`, `retrieval`, `api`, `core`).

**Why not the rung below (Rung 1, plain monolith):** the ingestion pipeline (offline, batch, heavy model loads) and the query API (online, latency-sensitive, SSE) have genuinely different runtime profiles and dependency footprints. Keeping them as separate packages with a shared `core` lets ingestion run as a one-shot container without dragging the web server's lifecycle around.

**Why not the rung above (Rung 3, service-oriented):** there's one owner and low QPS. Splitting retrieval and generation into separately deployed services would double operational complexity (network hops, independent deploys, distributed tracing across a boundary) to buy independence nobody needs yet. The package boundary is a seam I can cut later if retrieval ever needs to scale independently.

### B. Paradigm (KB §0.8)

**Primary paradigm: hybrid, organized as functional core, imperative shell (KB §0.8.4).**
**Rationale:** the retrieval and chunking logic is naturally pure — `chunk(document) -> list[Chunk]`, `fuse(bm25_hits, dense_hits) -> ranked`, `build_prompt(query, chunks) -> str` are all pure functions over immutable data, trivially unit-testable with no I/O. The imperative shell is thin: FastAPI handlers, the pgvector client, the model runtime. This is the same shape as the research-library-agent guide's "each node is a pure function over state, independently testable."

### C. Internal structure (KB §1, §1A)

**Internal structure: Layered, with vertical-slice packages.** Each package (`ingestion`, `retrieval`, `api`) is a feature slice; within each, a thin layer split (I/O adapter → service logic → pure functions). Not full hexagonal/DDD — the domain isn't complex enough to earn the ceremony (KB §1A.11 warns against hexagonal for simple shapes). The one port worth abstracting is the **embedder/reranker model interface**, so the same code runs against a local dockerized BGE and could later swap to an API without touching retrieval logic (the AgentRadar model-adapter pattern).

**Module boundaries:**
- `core` — pydantic models (`Chunk`, `Citation`, `RetrievalResult`), settings, the model-port protocol. No I/O.
- `ingestion` — parse → section-aware chunk (breadcrumb headers) → embed → upsert to pgvector + BM25 index.
- `retrieval` — hybrid fuse + rerank + prompt assembly.
- `api` — FastAPI, SSE endpoint, the grounding/guardrail prompt, disclaimer injection.

### D. Component patterns (KB §3–§8)

- **RAG two-pipeline (cloud-KB §Pattern 3):** offline ingestion pipeline builds the index; online query pipeline uses it. The core shape of the whole system.
- **Cache-Aside (KB §7.2):** cache `(query, jurisdiction) → reranked chunk IDs` and embedding results. Statute is near-static, so cache hit rate on repeat questions is high and the win is real.
- **Anti-Corruption Layer (KB §6.2) / model port:** the embedder+reranker sit behind one interface so local-vs-API is a config line, not a code change.
- **Rate Limiting (KB §5.x):** on the public query endpoint — an LLM endpoint with no limit is a cost-blowup waiting for a retry loop or abuse.
- **Retry with backoff + Timeout (KB §5.x):** around the model runtime calls.
- **API Gateway (KB §4) via nginx:** single port, `/api` → FastAPI, `/` → static frontend, SSE passthrough (buffering off).

---

## Diagrams

The index is the handoff point between two pipelines that run at different times. The **offline ingestion pipeline** builds the index ahead of time (`uv run ingest`, re-run only when a statute changes) — the user's question never flows through it. The **online request pipeline** hits the already-built index per request. The orchestration node marked "Retrieval orchestrator" is a fixed retrieve-then-generate step in v1 (classic RAG); it is also exactly where an **agent** would slot in later if eval shows one-shot retrieval failing (see Non-goals and Architecture · A). In the diagram below, the top chain (source docs → index) is the offline build; the bottom chain (question → SSE) is the online request path; the dotted edge is the request path reading the pre-built index.

```mermaid
flowchart TD
    SRC["source docs<br/>statute, CCRs, county code"] --> PARSE["chunk + embed<br/>section-aware, breadcrumb headers, BGE-M3"]
    PARSE --> IDX[("index: pgvector HNSW + BM25<br/>built offline by uv run ingest")]

    Q["user question<br/>browser to nginx :80"] --> ORCH["retrieval orchestrator<br/>agent slots in here later"]
    ORCH --> RET["retrieve tool: hybrid<br/>vector + BM25, top-20"]
    IDX -.->|read at request time| RET
    RET --> RR["rerank<br/>cross-encoder, top-5"]
    RR --> GEN["grounded answer<br/>citation-forced, guidance-not-advice"]
    GEN --> SSE["SSE stream to browser"]
```

**Editable source:** `docs/architecture.mermaid` in-repo.

---

## Interfaces

**Query endpoint (SSE):**
```
POST /api/ask
  body: { "question": str, "jurisdiction": "MD" }
  response: text/event-stream
    event: token   data: {"text": "..."}
    event: citation data: {"doc": "MD HOA Act", "section": "§11B-111", "url": "...", "snippet": "..."}
    event: done    data: {"disclaimer": "Informational only, not legal advice."}
```

**Core types (pydantic, in `core`):**
```python
class Citation(BaseModel):
    doc: str            # "Maryland HOA Act"
    section: str        # "§11B-111"
    breadcrumb: str     # "MD HOA Act › §11B-111 › Meetings — Notice"
    url: str | None
    snippet: str

class Chunk(BaseModel):
    id: str             # deterministic content hash (delta re-ingest key)
    text: str           # breadcrumb header + body
    embedding: list[float] | None
    citation: Citation
    jurisdiction: str = "MD"

class RetrievalResult(BaseModel):
    chunks: list[Chunk]
    scores: list[float]
```

**Model port (the swappable seam):**
```python
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> RetrievalResult: ...
```

**CLI:** `uv run ingest --source ./corpus/md-hoa-act.pdf` · `uv run serve`.

---

## Dependencies / infrastructure

- **Language:** Python 3.12 — near-irreversible; matches your stack, ecosystem for RAG (langchain, sentence-transformers) is Python-first.
- **Runtime / hosting:** single host, docker-compose (KB §2A — scale *up* before out; a modern box handles this workload with room to spare). No k8s.
- **Persistent storage:** **PostgreSQL 16 + pgvector (HNSW index)** — high-penalty choice, argued: one container serves both the vector store *and* the relational metadata/BM25-adjacent needs, keeping the data plane to a single service (the finradar simplification). pgvector at this corpus size (statute + docs, not millions of chunks) is comfortably within its sweet spot per KB §1.5.1. BM25 via Postgres full-text (`tsvector`) or a lightweight in-process index over the same rows — no separate search service.
- **Key third-party packages:** `sentence-transformers` / `FlagEmbedding` (BGE-M3 embed + BGE-reranker), `fastapi` + `sse-starlette`, `pydantic` / `pydantic-settings`, `psycopg` + `pgvector`, `pypdf` / `trafilatura` (PDF + HTML parsing per the research-library guide), `langgraph` (thin, leaves the agentic seam open).
- **Low-stakes / easily-swapped deps:** the generation LLM (local Ollama vs API) is one config line behind the model port — deliberately not over-specified.

---

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

## Security

- **Threats considered:** prompt injection via the question field (attempts to make the model drop the disclaimer or role-play a lawyer); cost-abuse (flood the LLM endpoint); malicious file at ingest time (only the maintainer ingests, so lower surface, but PDF parsing still runs untrusted-ish input).
- **Attack surface:** the public `POST /api/ask` field, and the ingestion parser.
- **Trust boundaries:** browser → nginx → FastAPI is the always-present one. The model runtime and pgvector sit on an internal docker network, not exposed.
- **§5A choices:** no user auth in v1 (public read-only advisory, no accounts) — recorded deliberately so a reviewer can challenge it. **Rate limiting** (§5.x) on `/api/ask` by IP. **Secrets management** (§5A.8): any API keys via env/`.env` not baked into images (multistage build keeps them out of layers). Injection mitigation: the grounding prompt is structurally separated from user input (XML-tagged context, user text quoted, not concatenated into instructions), and the disclaimer is appended by the *server* on the `done` event — the model cannot suppress it.

---

## Privacy

Questions may reveal a user's address or dispute details. v1 keeps this minimal: questions are **not persisted with identity**; logs store the question text and retrieval trace for debugging but **no IP-to-question linkage beyond short-lived rate-limit counters**, and PII is kept out of long-term logs. No accounts, so no stored profile. If per-user CC&R upload lands in v2, this section gets rewritten — that feature inherits a real privacy obligation.

---

## Legal / compliance considerations

This is the load-bearing section for this project. The system is explicitly designed to **avoid the unauthorized practice of law**: it provides information and citations, not advice or verdicts. Every response carries a server-appended disclaimer ("Informational only, not legal advice; consult a licensed Maryland attorney"). Source documents (Maryland statute, county code) are public records; CC&Rs ingested for v1 are only ones that are publicly recorded or the maintainer is authorized to use. **License:** intended open-source (MIT), stated so contributors know the terms. The "guidance not answer" behavior is not just product taste — it's the compliance boundary.

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
