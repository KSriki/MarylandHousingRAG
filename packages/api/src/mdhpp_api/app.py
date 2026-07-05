"""FastAPI application factory.

Minimal for now: a health endpoint so the container and reverse proxy have a
real target. Phase 3 adds the SSE /api/ask endpoint, grounding prompt, and
disclaimer injection on top of this same app.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="MDHousingPolicyPipeline API", version="0.1.0")

    @app.get("/api/healthz")
    def healthz() -> dict[str, str]:
        """Liveness probe. Used by the container healthcheck and the proxy."""
        return {"status": "ok"}

    return app


app = create_app()
