"""FastAPI application.

Endpoints:
- GET  /api/healthcheck — liveness probe
- POST /api/ask         — SSE: retrieve -> rerank -> grounded generation

The disclaimer is appended by the server on the `done` event so the model can't
suppress it via prompt injection — that placement is the compliance boundary.
Heavy models (embedder, reranker) load lazily on first request, not at import.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from mdhpp_core import Embedder, Generator, Reranker, load_settings


class AskRequest(BaseModel):
    question: str
    jurisdiction: str = "MD"


@dataclass
class _Components:
    embedder: Embedder
    reranker: Reranker
    generator: Generator


def create_app() -> FastAPI:
    app = FastAPI(title="MDHousingPolicyPipeline API", version="0.1.0")
    settings = load_settings()

    # Lazily-constructed singletons so import and healthcheck stay light.
    holder: dict[str, _Components] = {}

    def _components() -> _Components:
        if "c" not in holder:
            from mdhpp_retrieval import BGEM3Embedder, BGEReranker, make_generator

            holder["c"] = _Components(
                embedder=BGEM3Embedder(settings.embedding_model),
                reranker=BGEReranker(settings.reranker_model),
                generator=make_generator(settings),
            )
        return holder["c"]

    # Overridable seams for testing: point these at fakes to exercise the SSE
    # wiring without building real models or hitting the DB.
    from mdhpp_retrieval import retrieve as _retrieve

    app.state.components = _components
    app.state.retrieve = _retrieve

    @app.get("/api/healthcheck")
    def healthcheck() -> dict[str, str]:
        """Liveness probe. Used by the container healthcheck and the proxy."""
        return {"status": "ok"}

    @app.post("/api/ask")
    async def ask(req: AskRequest) -> EventSourceResponse:
        """Stream a grounded answer as Server-Sent Events."""
        components = app.state.components()
        retrieve = app.state.retrieve

        def event_stream() -> Iterator[dict[str, str]]:
            outcome = retrieve(
                req.question,
                settings,
                components.embedder,
                components.reranker,
                req.jurisdiction,
            )

            if not outcome.grounded:
                yield {
                    "event": "token",
                    "data": json.dumps(
                        {
                            "text": "I can't find governing policy for this in my "
                            "sources. Consider consulting a licensed Maryland "
                            "attorney or the relevant county office."
                        }
                    ),
                }
                yield {
                    "event": "done",
                    "data": json.dumps({"disclaimer": settings.disclaimer}),
                }
                return

            # Emit the citations up front so the UI can render source cards.
            for chunk in outcome.chunks:
                yield {
                    "event": "citation",
                    "data": json.dumps(
                        {
                            "doc": chunk.citation.doc,
                            "section": chunk.citation.section,
                            "url": chunk.citation.url,
                            "snippet": chunk.citation.snippet,
                        }
                    ),
                }

            for token in components.generator.generate(outcome.prompt):
                yield {"event": "token", "data": json.dumps({"text": token})}

            # Server-appended disclaimer: the model cannot suppress this.
            yield {
                "event": "done",
                "data": json.dumps({"disclaimer": settings.disclaimer}),
            }

        return EventSourceResponse(event_stream())

    return app


app = create_app()
