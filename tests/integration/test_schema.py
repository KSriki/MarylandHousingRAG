"""Integration tests for the pgvector data plane.

Marker-gated: these need the dockerized DB up (`docker compose up -d db`).
Run with `uv run pytest -m integration`.
"""

import psycopg
import pytest

from mdhpp_core import load_settings

pytestmark = pytest.mark.integration


@pytest.fixture
def conn() -> psycopg.Connection:
    settings = load_settings()
    try:
        c = psycopg.connect(settings.pg_dsn, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("pgvector data plane not reachable (docker compose up -d db)")
    with c:
        yield c


def test_vector_extension_installed(conn: psycopg.Connection) -> None:
    row = conn.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'").fetchone()
    assert row is not None


def test_chunks_table_exists(conn: psycopg.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'chunks'"
    ).fetchone()
    assert row is not None


def test_expected_indexes_present(conn: psycopg.Connection) -> None:
    rows = conn.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'chunks'").fetchall()
    names = {r[0] for r in rows}
    assert "chunks_embedding_hnsw" in names
    assert "chunks_ts_gin" in names
    assert "chunks_jurisdiction" in names


def test_tsvector_column_is_generated(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        INSERT INTO chunks (id, text, doc, section, breadcrumb, snippet)
        VALUES ('t1', 'meeting notice requirements', 'Doc', 'S1', 'B', 'snip')
        ON CONFLICT (id) DO NOTHING
        """
    )
    conn.commit()
    row = conn.execute(
        "SELECT ts @@ to_tsquery('english', 'notice') FROM chunks WHERE id = 't1'"
    ).fetchone()
    assert row is not None and row[0] is True
