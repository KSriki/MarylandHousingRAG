"""Integration test for hybrid retrieval — needs the ephemeral test plane.

Seeds a few chunks with known embeddings and text, then checks that
hybrid_search returns them ranked. Run via `make test-integration`.
"""

import psycopg
import pytest

from mdhpp_core import load_settings
from mdhpp_retrieval.hybrid import hybrid_search

pytestmark = pytest.mark.integration

_DIM = 1024


def _seed(dsn: str) -> None:
    """Insert two chunks: one about meetings, one about assessments."""
    with psycopg.connect(dsn) as conn:
        from pgvector.psycopg import register_vector

        register_vector(conn)
        conn.execute("DELETE FROM chunks")
        # Distinct embeddings so cosine can separate them.
        meet_vec = [1.0] + [0.0] * (_DIM - 1)
        assess_vec = [0.0, 1.0] + [0.0] * (_DIM - 2)
        for cid, body, sec, vec in [
            ("m", "Notice of a meeting shall be given to members.", "11B-111", meet_vec),
            ("a", "The association may levy special assessments.", "11B-112", assess_vec),
        ]:
            conn.execute(
                """
                INSERT INTO chunks (id, text, embedding, embedding_model,
                    jurisdiction, doc, section, breadcrumb, url, snippet)
                VALUES (%s,%s,%s,'m','MD',%s,%s,%s,NULL,%s)
                """,
                (cid, body, vec, "MD HOA Act", sec, f"MD HOA Act > {sec}", body),
            )
        conn.commit()


@pytest.fixture
def dsn() -> str:
    settings = load_settings()
    try:
        with psycopg.connect(settings.pg_dsn, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        pytest.skip("test pgvector not reachable (make test-integration)")
    _seed(settings.pg_dsn)
    return settings.pg_dsn


def test_lexical_match_retrieves_by_keyword(dsn: str) -> None:
    # Query text mentions "assessments" — lexical half should surface chunk "a".
    # Use a neutral non-zero vector (orthogonal to both chunks) so dense scores
    # are near-equal and the lexical half decides the ranking. A zero vector is
    # avoided: cosine distance to it is undefined.
    neutral = [0.0] * _DIM
    neutral[2] = 1.0  # a dimension neither seeded chunk uses
    result = hybrid_search(
        dsn=dsn,
        query_text="special assessments levy",
        query_embedding=neutral,
        top_k=5,
    )
    ids = [c.id for c in result.chunks]
    assert "a" in ids
    # The assessments chunk should outrank the meetings chunk on this query.
    assert ids.index("a") <= ids.index("m") if "m" in ids else True


def test_dense_match_retrieves_by_vector(dsn: str) -> None:
    # Query vector aligned with the meetings chunk's embedding.
    meet_vec = [1.0] + [0.0] * (_DIM - 1)
    result = hybrid_search(
        dsn=dsn,
        query_text="unrelated words",
        query_embedding=meet_vec,
        top_k=5,
    )
    assert result.chunks
    assert result.chunks[0].id == "m"


def test_returns_scores_aligned_with_chunks(dsn: str) -> None:
    result = hybrid_search(
        dsn=dsn,
        query_text="meeting notice",
        query_embedding=[1.0] + [0.0] * (_DIM - 1),
        top_k=5,
    )
    assert len(result.chunks) == len(result.scores)
