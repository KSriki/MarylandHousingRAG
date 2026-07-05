"""Implementation of `mdhpp serve`.

Runs the FastAPI app under uvicorn. Host/port are container-internal; the
reverse proxy (policy-proxy) fronts the app on :80.
"""

from __future__ import annotations


def run(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run("mdhpp_api.app:app", host=host, port=port, log_level="info")
