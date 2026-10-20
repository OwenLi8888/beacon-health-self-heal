"""Bad-fix rules (pivot v0.4 B4): a fixed sleep, or a positional pick for a multiple match, is never applied."""
from types import SimpleNamespace

import pytest

import policy

SRC = "def read():\n    table.wait_for()\n    rows = table.get_by_role('row').all()\n"
EMPTY_TABLE = "ValueNotFound: A1c result table has no rows"
TWO_PATIENTS = "AmbiguousValue: 2 patients named Rosa Delgado"


def _diag(patch):
    return SimpleNamespace(cause_category="script", confidence=0.9, patch=patch, touches_data_write=False,
                           proposed_decision="auto_apply")


def _decide(patch, first_error):
    return policy.decide(_diag(patch), 2, [2], SRC, True, True, first_error=first_error)


SLEEP = "@@\n     table.wait_for()\n+    time.sleep(4)\n"
WAIT_FOR_TIMEOUT = "@@\n     table.wait_for()\n+    chart.page.wait_for_timeout(4000)\n"
FIRST = "@@\n-    matches.click()\n+    matches.first.click()\n"
NTH = "@@\n-    matches.click()\n+    matches.nth(0).click()\n"
INDEX = "@@\n-    matches.click()\n+    matches.all()[-1].click()\n"
WAIT_ROWS = "@@\n     table.wait_for()\n+    table.get_by_role('row').filter(has=chart.get_by_role('cell')).first.wait_for()\n"
NAME_DOB = "@@\n-    matches.click()\n+    finder.get_by_role('row').filter(has=matches).filter(has_text=dob).click()\n"


@pytest.mark.parametrize("patch", [SLEEP, WAIT_FOR_TIMEOUT])
def test_fixed_sleep_rejected(patch):
    assert policy.bad_fix(patch, EMPTY_TABLE) == "fixed_sleep"
    assert _decide(patch, EMPTY_TABLE) == "rejected_bad_fix"


@pytest.mark.parametrize("patch", [FIRST, NTH, INDEX])
def test_positional_pick_rejected_for_multiple_match(patch):
    assert policy.bad_fix(patch, TWO_PATIENTS) == "positional_pick"
    assert _decide(patch, TWO_PATIENTS) == "rejected_bad_fix"
    assert _decide(patch, "Error: strict mode violation: locator resolved to 2 elements") == "rejected_bad_fix"


def test_explicit_wait_on_first_row_allowed_for_timing():
    assert policy.bad_fix(WAIT_ROWS, EMPTY_TABLE) is None
    assert _decide(WAIT_ROWS, EMPTY_TABLE) == "auto_apply"


def test_name_and_dob_allowed_for_multiple_match():
    assert _decide(NAME_DOB, TWO_PATIENTS) == "auto_apply"


def test_removed_lines_do_not_count():
    assert policy.bad_fix("@@\n-    rows[0].click()\n+    row.click()\n", TWO_PATIENTS) is None
