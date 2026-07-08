"""Section-aware parsing of legal source text (pure, no I/O).

Turns a document's raw text into a list of `Section` records, each with a
statute-style section reference and a breadcrumb path showing where it sits in
the document hierarchy. The file-reading (PDF/HTML -> text) happens in the
imperative shell (`readers.py`); this module only works on strings so it stays
pure and unit-testable.

Legal text is hierarchical: Title > Section > (heading). We detect section
headers like "§ 11B-111" or "11B-111." and the short heading that follows, then
attribute the body text between one header and the next to that section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Matches statute section refs: "§ 11B-111", "11B-111.", "§14-203", etc.
# Maryland's official PDFs use an EN-DASH (U+2013) in section numbers
# (e.g. section 11B followed by U+2013 then 104), not an ASCII hyphen, so the
# separator class accepts hyphen, en-dash, and em-dash. The captured ref is
# normalized to an ASCII hyphen in _normalize_ref so citations are consistent.
_DASHES = "\\-\u2013\u2014"  # -, en-dash, em-dash
_SECTION_RE = re.compile(
    rf"^\s*(?:§\s*)?(?P<ref>\d+[A-Za-z]?[{_DASHES}]\d+(?:\.\d+)?)\.?\s*(?P<heading>.*)$"
)


def _normalize_ref(ref: str) -> str:
    """Normalize a captured section ref to use ASCII hyphens.

    The source PDFs use en-dashes; downstream citations and chunk ids should be
    stable ASCII (e.g. "11B-111"), so callers and stored data don't depend on
    the source's dash style.
    """
    return ref.replace("\u2013", "-").replace("\u2014", "-")


@dataclass(frozen=True)
class Section:
    """One section of a document, ready to be chunked.

    `ref` is the bare section number (e.g. "11B-111"); `breadcrumb` is the full
    path used as the contextual chunk header (e.g. "MD HOA Act > 11B-111 >
    Meetings"); `body` is the section's text with the header line removed.
    """

    ref: str
    heading: str
    breadcrumb: str
    body: str


def parse_sections(text: str, doc_title: str) -> list[Section]:
    """Split document text into sections keyed by statute section headers.

    `doc_title` is the human document name (e.g. "MD HOA Act") that anchors each
    breadcrumb. Text before the first recognized section header is ignored
    (front matter / preamble); if no headers are found, the whole document is
    returned as a single unsectioned block under the doc title.
    """
    lines = text.splitlines()
    sections: list[Section] = []

    current_ref: str | None = None
    current_heading: str = ""
    current_body: list[str] = []

    def flush() -> None:
        if current_ref is None:
            return
        body = "\n".join(current_body).strip()
        crumb = _breadcrumb(doc_title, current_ref, current_heading)
        sections.append(
            Section(
                ref=current_ref,
                heading=current_heading,
                breadcrumb=crumb,
                body=body,
            )
        )

    for line in lines:
        m = _SECTION_RE.match(line)
        # Treat as a section header only if the ref looks like a real statute
        # number (contains a dash separator) and the line isn't absurdly long (a
        # paragraph that merely starts with a number). Accept any dash style;
        # the source PDFs use en-dashes.
        if m and any(d in m.group("ref") for d in ("-", "\u2013", "\u2014")) and len(line) < 120:
            flush()
            current_ref = _normalize_ref(m.group("ref"))
            current_heading = m.group("heading").strip()
            current_body = []
        elif current_ref is not None:
            current_body.append(line)

    flush()

    if not sections:
        # No section headers detected: keep the whole doc as one block so it's
        # still retrievable, rather than dropping it.
        return [
            Section(
                ref="",
                heading="",
                breadcrumb=doc_title,
                body=text.strip(),
            )
        ]

    return sections


def _breadcrumb(doc_title: str, ref: str, heading: str) -> str:
    """Build the contextual chunk header path.

    "MD HOA Act > 11B-111 > Meetings" — heading is dropped when absent.
    """
    parts = [doc_title, ref]
    if heading:
        parts.append(heading)
    return " > ".join(p for p in parts if p)
