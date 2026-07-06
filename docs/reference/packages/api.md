# mdhpp-api

The FastAPI application: the SSE query endpoint, the grounding prompt, and the
server-appended disclaimer. Fronted by nginx on :80 in the deployed stack.

## What's inside

| Endpoint | Purpose |
|---|---|
| `GET /api/healthcheck` | Liveness probe — used by the container healthcheck and the proxy |
| `POST /api/ask` | *(Phase 3)* SSE streaming: retrieve → rerank → grounded answer with forced citations |

## The disclaimer is server-owned

The "informational, not legal advice" disclaimer is appended by the server on
the SSE `done` event — the model cannot suppress it via prompt injection. That
placement is the compliance boundary, not a UX detail (see
[Security, privacy & legal](../../architecture/security-legal.md)).

## API reference

::: mdhpp_api.app
