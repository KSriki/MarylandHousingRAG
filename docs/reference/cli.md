# CLI

The `mdhpp` command is the unified operational entry point. Run `mdhpp --help`
for the current list of subcommands.

## Commands

### `mdhpp ingest`

Parse, chunk, embed, and delta-upsert source documents into pgvector.

```bash
mdhpp ingest                 # ingest everything under ./corpus
mdhpp ingest --source FILE   # ingest a single file
mdhpp ingest --corpus DIR    # ingest a specific directory
```

### `mdhpp serve`

Run the FastAPI app under uvicorn (the reverse proxy fronts it on :80).

```bash
mdhpp serve
```

### `mdhpp version`

Print the installed version.
