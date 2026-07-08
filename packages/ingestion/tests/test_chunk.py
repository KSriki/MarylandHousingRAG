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


def test_oversized_subsection_packs_whole_sentences() -> None:
    codec = _word_codec()
    # A single "(a)" subsection with several sentences, longer than chunk_size.
    body = "(a) " + " ".join(f"Clause {i} says something." for i in range(8))
    chunks = chunk_section(_section(body), "MD HOA Act", codec, chunk_size=10, overlap=3)
    # More than one chunk (it exceeded chunk_size), and no chunk splits a
    # sentence: every chunk ends at a sentence boundary (period).
    assert len(chunks) > 1
    for c in chunks:
        assert c.citation.snippet.rstrip().endswith(".")


def test_single_subsection_stays_intact() -> None:
    codec = _word_codec()
    # One short subsection well under chunk_size -> exactly one chunk, verbatim.
    body = "(b) A short operative rule."
    chunks = chunk_section(_section(body), "MD HOA Act", codec, chunk_size=50, overlap=10)
    assert len(chunks) == 1
    assert "A short operative rule." in chunks[0].citation.snippet


def test_empty_body_yields_no_chunks() -> None:
    codec = _word_codec()
    assert chunk_section(_section("   "), "MD HOA Act", codec, 10, 0) == []


def test_chunk_ids_are_deterministic() -> None:
    codec = _word_codec()
    a = chunk_section(_section("same text here"), "MD HOA Act", codec, 100, 0)
    b = chunk_section(_section("same text here"), "MD HOA Act", codec, 100, 0)
    assert a[0].id == b[0].id


def test_subsections_become_separate_chunks() -> None:
    codec = _word_codec()
    # Statute-shaped: subsections on their own lines (real PDF layout).
    body = (
        "(a) In this section the following words have meanings.\n"
        "(b) A restriction may not prohibit installation of a solar collector system.\n"
        "(c) This section does not apply to historic property."
    )
    chunks = chunk_section(_section(body), "MD HOA Act", codec, chunk_size=200, overlap=20)
    # Each subsection is its own focused chunk, not one blob.
    assert len(chunks) == 3
    snippets = [c.citation.snippet for c in chunks]
    # The operative rule stands alone (this is what lets the reranker score it).
    assert any("may not prohibit installation of a solar collector" in s for s in snippets)
    assert any(s.startswith("(a)") for s in snippets)
    assert any(s.startswith("(c)") for s in snippets)


def test_page_number_artifacts_are_stripped() -> None:
    codec = _word_codec()
    body = "(a) First clause of the rule.\n\n- 2 -\n\n(b) Second clause of the rule."
    chunks = chunk_section(_section(body), "MD HOA Act", codec, chunk_size=200, overlap=20)
    for c in chunks:
        assert "- 2 -" not in c.text


def test_enumerated_list_not_split_on_semicolons() -> None:
    """A colon-introduced list with semicolon-separated items is ONE sentence and
    must stay together — splitting on ; or : would orphan the list items."""
    codec = _word_codec()
    # One oversized subsection that is a single sentence with an enumerated list.
    body = (
        "(b) An unreasonable limitation includes a limitation that: "
        "(i) significantly increases the cost of the solar collector system; or "
        "(ii) significantly decreases the efficiency of the solar collector system."
    )
    # chunk_size large enough to hold it whole -> exactly one chunk, list intact.
    chunks = chunk_section(_section(body), "MD HOA Act", codec, chunk_size=200, overlap=20)
    assert len(chunks) == 1
    snip = chunks[0].citation.snippet
    # the governing clause and both list items stay in the same chunk
    assert "limitation that:" in snip
    assert "increases the cost" in snip
    assert "decreases the efficiency" in snip
