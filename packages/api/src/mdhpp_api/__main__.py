"""Entry point for `serve` (see api pyproject [project.scripts]).

Runs the FastAPI app under uvicorn. Host/port are fixed to the container's
internal interface; the reverse proxy (policy-proxy) fronts it on :80.
"""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "mdhpp_api.app:app",
        host="0.0.0.0",  # container-internal; the proxy fronts it on :80
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
