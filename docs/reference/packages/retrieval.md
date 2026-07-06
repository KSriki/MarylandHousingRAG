# mdhpp-retrieval

The online retrieval layer: given a question, find the chunks that answer it,
rerank them, and assemble a grounded prompt (or signal a refusal). Hybrid
retrieval (dense + lexical) → cross-encoder rerank → relevance-floor check. See
the [Retrieval architecture](../../architecture/retrieval.md) page for the
conceptual explanation.

## What's inside

| Module | Layer | Purpose |
|---|---|---|
| `hybrid` | shell | One SQL query fusing pgvector cosine similarity + `tsvector` keyword rank |
| `rerank` | shell | `BGEReranker` cross-encoder re-scoring (core `Reranker` port, lazy weights) |
| `embed` | shell | `BGEM3Embedder` for query embedding (core `Embedder` port) |
| `generate` | shell | `OllamaGenerator` + `make_generator` factory (core `Generator` port) |
| `prompt` | pure | Grounded-prompt assembly + the relevance-floor grounding check |
| `orchestrator` | shell | Ties it together: embed → hybrid → rerank → floor → prompt |

## The grounding floor

If the best rerank score is below `settings.relevance_floor`, `retrieve` returns
`grounded=False` and the API refuses ("can't find it in the sources") instead of
letting the model improvise. This is what keeps the system from inventing law.

## Provider-agnostic generation

`make_generator` picks the LLM from settings (`llm_provider`), defaulting to
local Ollama. Swapping to an API provider is a config change plus one new
`Generator` implementation — no change to retrieval or the API.

## API reference

::: mdhpp_retrieval
