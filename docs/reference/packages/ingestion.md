# mdhpp-ingestion

The offline pipeline: turn source documents into indexed, embedded chunks in
pgvector. Runs on demand via `mdhpp ingest`, not in the request path. Follows
functional-core / imperative-shell — the parse and chunk stages are pure and
unit-tested; the readers, embedder, and store do the I/O.

## What's inside

| Module | Layer | Purpose |
|---|---|---|
| `parse` | pure | Section-aware parsing — detects statute headers (`§ 11B-111`), builds breadcrumb paths |
| `chunk` | pure | Token-bounded chunking with breadcrumb headers prepended; deterministic ids |
| `readers` | shell | PDF (pypdf) / HTML (trafilatura) → plain text |
| `embed` | shell | `BGEM3Embedder` implementing the core `Embedder` port (lazy weight load) |
| `store` | shell | Delta upsert + prune to pgvector, keyed on content hash |
| `pipeline` | shell | Orchestrates read → parse → chunk → embed → upsert |

## The delta-upsert idea

A chunk's id is a hash of its breadcrumb + body. Re-running ingestion on an
amended statute produces the *same* id for unchanged chunks and a *new* id for
changed ones, so `upsert_chunks` rewrites only what changed and `prune_missing`
removes sections deleted from the source. Re-ingestion is a diff, not a rebuild.

## Breadcrumb headers

Each chunk is prefixed with its hierarchy path (e.g.
`MD HOA Act > 11B-111 > Meetings`) before embedding. Both the vector and the LLM
then see *where* a passage sits — the single biggest retrieval-quality lever for
hierarchical legal text. The citation snippet stores only the body, so users see
the actual statute text, not the header.

## API reference

::: mdhpp_ingestion
