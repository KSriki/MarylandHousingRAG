"""Unit tests for the pure core — no I/O, no external services."""

import pytest

from mdhpp_core import Chunk, Citation, RetrievalResult, chunk_id
from mdhpp_core.settings import Settings

pytestmark = pytest.mark.unit


def _citation() -> Citation:
    return Citation(
        doc="Maryland HOA Act",
        section="RP 11B-111",
        breadcrumb="MD HOA Act > 11B-111 > Meetings",
        url=None,
        snippet="Notice of a meeting shall be given...",
    )


def test_chunk_id_is_deterministic() -> None:
    a = chunk_id("MD HOA Act > 11B-111", "same body")
    b = chunk_id("MD HOA Act > 11B-111", "same body")
    assert a == b


def test_chunk_id_changes_with_content() -> None:
    base = chunk_id("MD HOA Act > 11B-111", "body one")
    changed_body = chunk_id("MD HOA Act > 11B-111", "body two")
    changed_crumb = chunk_id("MD HOA Act > 11B-112", "body one")
    assert base != changed_body
    assert base != changed_crumb


def test_retrieval_result_top_truncates() -> None:
    chunks = [Chunk(id=str(i), text=f"c{i}", citation=_citation()) for i in range(10)]
    result = RetrievalResult(chunks=chunks, scores=[float(i) for i in range(10)])
    top3 = result.top(3)
    assert len(top3.chunks) == 3
    assert len(top3.scores) == 3
    assert top3.chunks[0].id == "0"


def test_settings_dsn_builds() -> None:
    s = Settings(pg_host="db", pg_port=5432, pg_db="mdhpp", pg_user="u", pg_password="p")
    assert s.pg_dsn == "postgresql://u:p@db:5432/mdhpp"
