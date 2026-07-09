"""Out-of-jurisdiction detection (pure, no I/O).

The corpus is Maryland statute. A question that explicitly names another US
state ("HOA rules in California") is topically an HOA question — so the reranker
gives it a nonzero score and it can slip past the relevance floor — but the
answer would wrongly cite Maryland law for another state. This module flags such
questions so the orchestrator can decline with a jurisdiction-specific message
instead of answering.

Detection is deliberately conservative: it fires only when another state is
named explicitly. A bare question with no state mentioned is assumed to be about
Maryland (the tool's scope) and is NOT flagged.
"""

from __future__ import annotations

import re

# US states + DC, excluding Maryland (and its abbreviation), lowercased.
_OTHER_STATES = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
    "district of columbia",
}


def detect_other_state(question: str) -> str | None:
    """Return the name of another US state named in the question, or None.

    Matches on whole words so "washington" isn't found inside a longer token and
    "virginia" doesn't fire on "west virginia" being present (that's handled by
    matching the longer name too). Case-insensitive.
    """
    q = question.lower()
    # Check multi-word states first so "west virginia" wins over "virginia".
    for state in sorted(_OTHER_STATES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(state)}\b", q):
            return state
    return None
