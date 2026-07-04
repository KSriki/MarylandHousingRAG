-- Auto-applied by the postgres init sidecar on first boot (see docker-compose).
-- Idempotent so a re-run (or a fresh volume) rebuilds cleanly.

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per indexed chunk. `id` is the deterministic content hash from
-- mdhpp_core.hashing, so re-ingestion is a delta upsert, not a full rebuild.
CREATE TABLE IF NOT EXISTS chunks (
    id              TEXT PRIMARY KEY,
    text            TEXT NOT NULL,
    embedding       VECTOR(1024),               -- BGE-M3 default dim
    embedding_model TEXT,                        -- model+version (re-index key)
    jurisdiction    TEXT NOT NULL DEFAULT 'MD',
    doc             TEXT NOT NULL,               -- 'Maryland HOA Act'
    section         TEXT NOT NULL,               -- 'RP 11B-111'
    breadcrumb      TEXT NOT NULL,               -- full hierarchy path
    url             TEXT,
    snippet         TEXT NOT NULL,               -- supporting text for the citation
    -- Generated tsvector for the lexical (BM25-adjacent) half of hybrid search.
    ts              TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dense retrieval: HNSW over cosine distance. Tune m / ef_construction as the
-- corpus grows; these are sane defaults for a statute-sized index.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Lexical retrieval: GIN over the generated tsvector.
CREATE INDEX IF NOT EXISTS chunks_ts_gin
    ON chunks USING gin (ts);

-- Pre-retrieval metadata filter (jurisdiction=MD for v1).
CREATE INDEX IF NOT EXISTS chunks_jurisdiction
    ON chunks (jurisdiction);
