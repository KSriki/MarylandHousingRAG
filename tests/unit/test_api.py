"""Unit tests for the API app — no external services.

Uses httpx's ASGITransport to drive the app in-process, avoiding Starlette's
TestClient (which is tightly coupled to specific httpx versions).
"""

import httpx
import pytest

from mdhpp_api.app import app

pytestmark = pytest.mark.unit


async def test_healthcheck_returns_ok() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/healthcheck")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
