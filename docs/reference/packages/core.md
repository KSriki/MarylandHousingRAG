# mdhpp-core

The base layer. Owns the canonical domain types, environment-driven settings,
and the model port (the embedder/reranker protocols). Everything else in the
codebase imports from here, and this package imports nothing from the others.

No I/O, no third-party clients, no framework coupling — just data shapes,
configuration, and the protocols that keep concrete implementations swappable.
That purity is what makes the whole system unit-testable: the parse/chunk/prompt
logic is pure functions over these types.

## What's inside

| Module | Purpose |
|---|---|
| `models` | Pydantic models — `Chunk`, `Citation`, `RetrievalResult` — the data that flows through ingestion and retrieval |
| `settings` | `Settings` (pydantic-settings): DB connection, model names, chunking + retrieval knobs, the disclaimer — all env-overridable via `MDHPP_*` |
| `ports` | `Embedder` and `Reranker` protocols — the swappable seam so local BGE vs an API is a wiring change, not a code change |
| `hashing` | `chunk_id` — deterministic content hash so re-ingestion is a delta update, not a full rebuild |

## When to import what

```python
# Domain types
from mdhpp_core import Chunk, Citation, RetrievalResult

# Settings — loaded once in the shell, passed down
from mdhpp_core import Settings, load_settings

# The model port — depend on the protocol, not a concrete embedder
from mdhpp_core import Embedder, Reranker

# Deterministic chunk identity
from mdhpp_core import chunk_id
```

## Why the model port matters

`Embedder` and `Reranker` are `Protocol`s, not base classes. Ingestion and
retrieval depend on the protocol; the concrete BGE-M3 embedder lives in the
ingestion package. This is the anti-corruption seam from the design doc — swap
local models for an API by changing one line in the imperative shell, without
touching any retrieval logic.

## API reference

::: mdhpp_core
