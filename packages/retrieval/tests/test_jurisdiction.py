"""Unit tests for out-of-jurisdiction detection (pure, no I/O)."""

import pytest

from mdhpp_retrieval.jurisdiction import detect_other_state

pytestmark = pytest.mark.unit


def test_flags_other_state_named() -> None:
    assert detect_other_state("What are the HOA rules in California?") == "california"


def test_flags_case_insensitively() -> None:
    assert detect_other_state("hoa fines in TEXAS") == "texas"


def test_multiword_state_wins_over_substring() -> None:
    # "west virginia" must win over "virginia"
    assert detect_other_state("HOA law in West Virginia") == "west virginia"


def test_maryland_question_not_flagged() -> None:
    assert detect_other_state("Can my HOA fine me in Maryland?") is None


def test_bare_question_not_flagged() -> None:
    # No state named -> assumed Maryland (tool scope), not flagged.
    assert detect_other_state("Can my HOA stop me from installing solar panels?") is None


def test_does_not_fire_on_substring() -> None:
    # "washington" shouldn't be found inside an unrelated longer word.
    assert detect_other_state("The washingtonian newsletter") is None
