# Packages

The codebase is a uv workspace of four packages plus a root CLI. Each page below
is a hand-written guide (what the package is for, how its pieces fit) followed by
an auto-generated API reference pulled from the source docstrings.

| Package | Role |
|---|---|
| [mdhpp-core](core.md) | Shared models, settings, and the model port. No I/O. Everything imports from here. |
| [mdhpp-ingestion](ingestion.md) | Offline pipeline: parse → chunk → embed → delta upsert. Run via `mdhpp ingest`. |
| [mdhpp-retrieval](retrieval.md) | Online hybrid retrieval + rerank + grounded prompt assembly. |
| [mdhpp-api](api.md) | FastAPI SSE app: the `/api/ask` endpoint and the disclaimer boundary. |

The dependency flow is one-directional: `core` ← `ingestion`, `retrieval` ←
`api`. Nothing depends back on the root CLI (`src/mdhpp`), which is dispatch only.
