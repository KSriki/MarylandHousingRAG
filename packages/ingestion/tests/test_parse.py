"""Unit tests for the pure section parser — no I/O, no models."""

import pytest

from mdhpp_ingestion.parse import parse_sections

pytestmark = pytest.mark.unit


def test_parses_sections_with_refs_and_breadcrumbs() -> None:
    text = (
        "§ 11B-111. Meetings\n"
        "Notice of a meeting shall be given to each member.\n"
        "§ 11B-112. Assessments\n"
        "The association may levy assessments.\n"
    )
    sections = parse_sections(text, doc_title="MD HOA Act")
    assert len(sections) == 2
    assert sections[0].ref == "11B-111"
    assert sections[0].heading == "Meetings"
    assert sections[0].breadcrumb == "MD HOA Act > 11B-111 > Meetings"
    assert "Notice of a meeting" in sections[0].body
    assert sections[1].ref == "11B-112"


def test_body_excludes_the_header_line() -> None:
    text = "§ 14-203. Liens\nA lien attaches upon recording.\n"
    (section,) = parse_sections(text, doc_title="Contract Lien Act")
    assert "14-203" not in section.body
    assert section.body.strip() == "A lien attaches upon recording."


def test_preamble_before_first_section_is_ignored() -> None:
    text = (
        "This document is provided for informational purposes.\n"
        "§ 11-101. Definitions\n"
        "In this title the following words have the meanings indicated.\n"
    )
    sections = parse_sections(text, doc_title="MD Condominium Act")
    assert len(sections) == 1
    assert sections[0].ref == "11-101"
    assert "informational purposes" not in sections[0].body


def test_no_headers_returns_single_block() -> None:
    text = "Just some ordinance text with no section markers at all."
    (section,) = parse_sections(text, doc_title="County Ordinance")
    assert section.ref == ""
    assert section.breadcrumb == "County Ordinance"
    assert "ordinance text" in section.body


def test_long_line_starting_with_number_is_not_a_header() -> None:
    long_para = "12-345 " + "word " * 40  # >120 chars, not a real header
    text = f"§ 11B-101. Scope\n{long_para}\n"
    sections = parse_sections(text, doc_title="MD HOA Act")
    # Only the real header creates a section; the long line stays as body.
    assert len(sections) == 1
    assert sections[0].ref == "11B-101"
