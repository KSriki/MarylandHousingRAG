# mdhpp-retrieval

The online retrieval layer: given a question, find the chunks that answer it and
assemble a grounded prompt. Hybrid retrieval (dense + lexical) followed by
cross-encoder reranking. See the [Retrieval architecture](../../architecture/retrieval.md)
page for the conceptual explanation.

> Implemented in Phase 3. This page will fill in as the package lands.

## Planned shape

| Module | Purpose |
|---|---|
| `hybrid` | Single SQL query scoring pgvector cosine similarity + `tsvector` keyword rank |
| `rerank` | BGE cross-encoder re-scoring the top-k candidates (core `Reranker` port) |
| `prompt` | Grounded-prompt assembly: XML-tagged context + the guidance-not-verdict instruction |

## API reference

::: mdhpp_retrieval
