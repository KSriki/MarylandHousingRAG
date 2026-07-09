# Retrieval

## Scenarios

**Scenario: answerable question with a clean citation**
1. User types "Can my HOA stop me from installing solar panels?"
2. Query is embedded (BGE-M3) and, in the same SQL, scored against the chunks' `tsvector` full-text index; hybrid fusion returns top-20 candidate chunks filtered to `jurisdiction=MD`.
3. BGE-reranker re-scores each candidate against the full chunk text (not just the snippet, at `max_length=1024`); top-5 above the relevance floor pass to the LLM as XML-tagged context, each carrying its breadcrumb header and citation.
4. LLM streams (SSE) a plain-language summary of the rule, notes Maryland limits an HOA's ability to prohibit solar, and cites the controlling Real Property section — framed as "here's what the law says," not "you're allowed."
5. UI renders the streamed answer with the citation as a clickable source card, plus the standing "informational, not legal advice" banner.

**Scenario: question the corpus can't support**
1. User asks about a niche tax-lien interaction not in the ingested corpus.
2. Hybrid retrieval + rerank return only low-score chunks (below the relevance floor).
3. The generation prompt's grounding rule triggers: the model responds that it can't find governing policy for this in its sources and suggests consulting an attorney or the specific county office — it does **not** improvise a rule.

**Scenario: re-ingestion after an amendment**
1. Maintainer drops an updated statute PDF into the source folder and runs `uv run ingest`.
2. Ingestion parses → subsection-aware chunks (split at `(a)/(b)/(c)` boundaries, PDF artifacts stripped) with breadcrumb headers → embeds → upserts into pgvector by stable content hash, replacing changed chunks only and skipping re-embedding of unchanged ones (delta update, not full rebuild).

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


## Hybrid retrieval: dense + lexical

Retrieval combines two complementary matching strategies, because legal text
needs both.

**Dense (semantic) retrieval.** The BGE-M3 embedder turns text into ~1024-dim
vectors capturing meaning; similar meaning lands nearby in vector space. A query
like "can they stop me from installing solar" matches a passage about
"restrictions on solar collectors" even with no shared words. Runs via pgvector's
HNSW index over cosine distance. Strength: paraphrase and concept. Weakness:
blurs exact tokens.

**Lexical (BM25-style) retrieval.** Keyword matching weighted so rare terms
(section numbers like `11B-111`, defined terms like "estoppel") count more than
common ones. Strength: exact tokens and citations — precisely what a user needs
to act. Weakness: literal (won't match synonyms).

Pure vector alone would land in the right neighborhood but sometimes miss the
exact section a user needs; pure lexical would miss paraphrased questions. Hybrid
runs both, merges, then reranks.

## Decision: lexical search via Postgres `tsvector`

The BM25 half runs **inside Postgres** using the generated `tsvector` column and
GIN index (see the schema), not an in-process library or a separate search
service.

Rationale:

- **Single data plane.** The project already committed to one Postgres for
  vectors + metadata (the reason pgvector was chosen over Qdrant). Keeping
  lexical search there too means no second retrieval system to run, memorize, or
  keep in sync.
- **One query.** The hybrid score (vector similarity + keyword rank) can be
  computed in a single SQL statement, rather than fetching from two systems and
  merging in application code.
- **No added process memory.** An in-process `rank_bm25` index would load the
  whole corpus into the API process's RAM and rebuild on every restart — extra
  pressure on the same process that (with local generation) is already
  memory-hungry.

Trade-off: Postgres full-text ranking is a slightly simpler function than
textbook BM25, but for a statute-sized corpus the quality difference is
negligible and the simplicity win is large. If exact-term retrieval quality ever
proves lacking, pgvector's newer ranking extensions are the revisit path
(measure first — see Decisions).
