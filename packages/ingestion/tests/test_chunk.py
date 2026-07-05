"""Unit tests for the pure chunker — uses a fake tokenizer, no models."""

import pytest

from mdhpp_ingestion.chunk import TokenCodec, chunk_section
from mdhpp_ingestion.parse import Section

pytestmark = pytest.mark.unit


def _word_codec() -> TokenCodec:
    """A trivial tokenizer: one token per whitespace word. Deterministic and
    dependency-free, so chunk-boundary logic is testable without tiktoken."""

    def encode(text: str) -> list[int]:
        # Map words to fake ids by index; decode reverses via a shared list.
        words = text.split()
        encode.words = words  # type: ignore[attr-defined]
        return list(range(len(words)))

    def decode(ids: list[int]) -> str:
        words = encode.words  # type: ignore[attr-defined]
        return " ".join(words[i] for i in ids)

    return TokenCodec(encode=encode, decode=decode)


def _section(body: str) -> Section:
    return Section(
        ref="11B-111",
        heading="Meetings",
        breadcrumb="MD HOA Act > 11B-111 > Meetings",
        body=body,
    )


def test_chunk_prepends_breadcrumb_header() -> None:
    codec = _word_codec()
    section = _section("one two three four five")
    chunks = chunk_section(section, "MD HOA Act", codec, chunk_size=100, overlap=0)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("MD HOA Act > 11B-111 > Meetings\n\n")


def test_snippet_is_body_only_not_header() -> None:
    codec = _word_codec()
    chunks = chunk_section(_section("alpha beta"), "MD HOA Act", codec, 100, 0)
    assert chunks[0].citation.snippet == "alpha beta"
    assert "MD HOA Act" not in chunks[0].citation.snippet


def test_long_body_splits_into_multiple_chunks() -> None:
    codec = _word_codec()
    body = " ".join(f"w{i}" for i in range(25))
    chunks = chunk_section(_section(body), "MD HOA Act", codec, chunk_size=10, overlap=0)
    # 25 tokens / step 10 -> 3 chunks (10, 10, 5)
    assert len(chunks) == 3


def test_overlap_carries_tokens_between_chunks() -> None:
    codec = _word_codec()
    body = " ".join(f"w{i}" for i in range(20))
    chunks = chunk_section(_section(body), "MD HOA Act", codec, chunk_size=10, overlap=3)
    # step = 10 - 3 = 7; starts at 0, 7, 14 -> 3 chunks
    assert len(chunks) == 3
    # the last 3 tokens of chunk 0 reappear at the start of chunk 1's body
    assert "w7 w8 w9" in chunks[1].citation.snippet


def test_empty_body_yields_no_chunks() -> None:
    codec = _word_codec()
    assert chunk_section(_section("   "), "MD HOA Act", codec, 10, 0) == []


def test_chunk_ids_are_deterministic() -> None:
    codec = _word_codec()
    a = chunk_section(_section("same text here"), "MD HOA Act", codec, 100, 0)
    b = chunk_section(_section("same text here"), "MD HOA Act", codec, 100, 0)
    assert a[0].id == b[0].id
