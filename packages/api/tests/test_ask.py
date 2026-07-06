"""Unit tests for the SSE /api/ask endpoint.

Retrieval and generation are injected via app.state, so these run with no DB and
no models — they exercise the streaming wiring, citation events, the refusal
path, and the server-appended disclaimer.
"""

from collections.abc import Iterator

import httpx
import pytest

import mdhpp_api.app as appmod
from mdhpp_core import Chunk, Citation
from mdhpp_retrieval.orchestrator import RetrievalOutcome

pytestmark = pytest.mark.unit


def _chunk() -> Chunk:
    return Chunk(
        id="1",
        text="ctx",
        citation=Citation(
            doc="MD HOA Act",
            section="11B-111",
            breadcrumb="MD HOA Act > 11B-111 > Meetings",
            url=None,
            snippet="Notice must be given.",
        ),
    )


class _FakeGen:
    def generate(self, prompt: str) -> Iterator[str]:
        yield "The law "
        yield "says notice is required."


class _FakeComponents:
    embedder = object()
    reranker = object()
    generator = _FakeGen()


def _app_with(outcome: RetrievalOutcome) -> object:
    app = appmod.create_app()
    app.state.components = lambda: _FakeComponents()
    app.state.retrieve = lambda *a, **k: outcome
    return app


async def _collect(app: object, question: str) -> str:
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        client.stream("POST", "/api/ask", json={"question": question}) as resp,
    ):
        lines = [line async for line in resp.aiter_lines()]
    return "\n".join(lines)


async def test_grounded_answer_streams_citation_tokens_and_disclaimer() -> None:
    app = _app_with(RetrievalOutcome(grounded=True, prompt="P", chunks=[_chunk()]))
    body = await _collect(app, "can they fine me?")
    assert "citation" in body
    assert "11B-111" in body
    assert "notice is required" in body
    assert "disclaimer" in body


async def test_refusal_when_not_grounded() -> None:
    app = _app_with(RetrievalOutcome(grounded=False, prompt="", chunks=[]))
    body = await _collect(app, "off-corpus question")
    assert "can't find" in body.lower()
    assert "disclaimer" in body
    # No citations emitted on the refusal path.
    assert "citation" not in body
