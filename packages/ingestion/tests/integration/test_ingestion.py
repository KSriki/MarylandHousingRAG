"""Integration tests for the delta upsert — needs the ephemeral test plane.

Run via `make test-integration` (brings up docker-compose.test.yml on :5433).
"""

import psycopg
import pytest

from mdhpp_core import Chunk, Citation, load_settings
from mdhpp_ingestion.store import prune_missing, upsert_chunks

pytestmark = pytest.mark.integration

_DIM = 1024


def _chunk(cid: str, body: str, doc: str = "Test Doc") -> Chunk:
    return Chunk(
        id=cid,
        text=f"{doc} > 1-1 > H\n\n{body}",
        citation=Citation(
            doc=doc,
            section="1-1",
            breadcrumb=f"{doc} > 1-1 > H",
            url=None,
            snippet=body,
        ),
        jurisdiction="MD",
        embedding=[0.0] * _DIM,
    )


@pytest.fixture
def dsn() -> str:
    settings = load_settings()
    try:
        with psycopg.connect(settings.pg_dsn, connect_timeout=2) as c:
            c.execute("DELETE FROM chunks")  # clean slate
            c.commit()
    except psycopg.OperationalError:
        pytest.skip("test pgvector not reachable (make test-integration)")
    return settings.pg_dsn


def test_upsert_inserts_chunks(dsn: str) -> None:
    written = upsert_chunks(dsn, [_chunk("a", "alpha"), _chunk("b", "beta")], "m")
    assert written == 2
    with psycopg.connect(dsn) as c:
        (count,) = c.execute("SELECT count(*) FROM chunks").fetchone()
    assert count == 2


def test_upsert_is_idempotent(dsn: str) -> None:
    upsert_chunks(dsn, [_chunk("a", "alpha")], "m")
    upsert_chunks(dsn, [_chunk("a", "alpha")], "m")  # same id
    with psycopg.connect(dsn) as c:
        (count,) = c.execute("SELECT count(*) FROM chunks").fetchone()
    assert count == 1


def test_prune_removes_stale_chunks(dsn: str) -> None:
    upsert_chunks(dsn, [_chunk("a", "alpha"), _chunk("b", "beta")], "m")
    # Re-ingest keeps only "a"; "b" should be pruned.
    pruned = prune_missing(dsn, "Test Doc", keep_ids=["a"])
    assert pruned == 1
    with psycopg.connect(dsn) as c:
        rows = c.execute("SELECT id FROM chunks WHERE doc = 'Test Doc'").fetchall()
    assert {r[0] for r in rows} == {"a"}
