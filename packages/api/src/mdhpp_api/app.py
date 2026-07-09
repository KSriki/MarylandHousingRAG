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
from mdhpp_retrieval import GenerationError


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

    @app.get("/api/sources")
    def sources() -> dict[str, list[dict[str, object]]]:
        """List the documents in the corpus, with chunk counts.

        Powers the sources browser so users can see what the system knows
        before asking. Reads distinct docs from the index.
        """
        import psycopg

        try:
            with psycopg.connect(settings.pg_dsn, connect_timeout=2) as conn:
                rows = conn.execute(
                    """
                    SELECT doc, jurisdiction, count(*) AS chunks,
                           count(DISTINCT section) AS sections
                    FROM chunks
                    GROUP BY doc, jurisdiction
                    ORDER BY doc
                    """
                ).fetchall()
        except psycopg.OperationalError:
            return {"sources": []}

        return {
            "sources": [
                {
                    "doc": r[0],
                    "jurisdiction": r[1],
                    "chunks": r[2],
                    "sections": r[3],
                }
                for r in rows
            ]
        }

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
                if outcome.refusal_reason == "jurisdiction":
                    refusal_text = (
                        "This tool only covers Maryland housing law. Your question "
                        "appears to be about another state, and HOA/condominium rules "
                        "differ by state — so I can't answer it from my sources. "
                        "Consult that state's statutes or a licensed attorney there."
                    )
                else:
                    refusal_text = (
                        "I can't find governing policy for this in my sources. My "
                        "sources are Maryland state statute (the HOA, Condominium, and "
                        "Contract Lien Acts), which set the rules an association must "
                        "follow — but many specifics (fences, paint colors, parking, "
                        "landscaping) are set by your community's own recorded "
                        "covenants (CC&Rs), which I don't have. Check your community's "
                        "declaration and bylaws, or consult a licensed Maryland "
                        "attorney or the relevant county office."
                    )
                yield {
                    "event": "token",
                    "data": json.dumps({"text": refusal_text}),
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

            # Signal generation is starting. Fills the gap between citations
            # appearing and the first token (the model's first-token latency),
            # so the UI can show progress instead of dead air.
            yield {"event": "status", "data": json.dumps({"stage": "generating"})}

            first_token_seen = False
            try:
                for token in components.generator.generate(outcome.prompt):
                    first_token_seen = True
                    yield {"event": "token", "data": json.dumps({"text": token})}
            except GenerationError as exc:
                first_token_seen = True
                yield {
                    "event": "token",
                    "data": json.dumps({"text": f"\n\n[The answer could not be generated. {exc}]"}),
                }

            # Retrieval cleared the floor (citations shown) but the model produced
            # nothing usable — tell the user rather than leaving a blank answer.
            if not first_token_seen:
                yield {
                    "event": "token",
                    "data": json.dumps(
                        {
                            "text": "I found related sections (see the sources) but "
                            "couldn't extract a clear answer from them. The precise "
                            "governing provision may be elsewhere; consider "
                            "consulting a licensed Maryland attorney."
                        }
                    ),
                }

            # Server-appended disclaimer: the model cannot suppress this.
            yield {
                "event": "done",
                "data": json.dumps({"disclaimer": settings.disclaimer}),
            }

        return EventSourceResponse(event_stream())

    return app


app = create_app()
