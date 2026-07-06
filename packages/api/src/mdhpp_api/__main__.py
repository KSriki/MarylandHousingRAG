"""Entry point for the API.

Exposed two ways: the `serve` console script (api pyproject [project.scripts])
and `mdhpp serve` (the umbrella CLI, which calls this). Also runnable as
`python -m mdhpp_api`. Runs the FastAPI app under uvicorn; host/port are
container-internal and the reverse proxy fronts it on :80.
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
