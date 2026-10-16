from datetime import date, datetime
from decimal import Decimal

import pytest

from oracle.s1_read_a1c import OracleError, check, expected_latest

D1, D2 = datetime(2026, 1, 2, 9, 0), datetime(2026, 3, 4, 9, 0)


def test_latest_by_date_not_row_order():
    assert expected_latest([(D2, "6.1"), (D1, "6.4")]) == (Decimal("6.1"), D2.date())
    assert expected_latest([(D1, "6.4"), (D2, "6.1")]) == (Decimal("6.1"), D2.date())


@pytest.mark.parametrize("rows", [
    [],                            # no A1c
    [(D2, ""), (D1, "6.4")],       # latest value empty
    [(D2, "high"), (D1, "6.4")],   # latest value not a number
    [(D2, "NaN")],                 # parses as Decimal, still not a value
    [(D2, "6.1"), (D2, "6.4")],    # tie on latest date
    [(None, "6.1"), (D1, "6.4")],  # missing date
])
def test_raises_instead_of_guessing(rows):
    with pytest.raises(OracleError):
        expected_latest(rows)


# Live DB (make reset first): values from env/seed/seed.sql.

def test_accepts_correct_reading():
    assert check("Rosa", "Delgado", Decimal("6.9"), date(2026, 4, 8))[0]


@pytest.mark.parametrize("value, day", [
    (Decimal("5.4"), date(2026, 2, 11)),  # Elena Delgado's real reading: wrong patient
    (Decimal("7.9"), date(2025, 4, 2)),   # Rosa's oldest A1c, not her latest
    (Decimal("6.9"), date(2026, 4, 9)),   # right value, wrong date
])
def test_rejects_wrong_reading(value, day):
    assert not check("Rosa", "Delgado", value, day)[0]


def test_no_a1c_patient_has_no_verdict():
    with pytest.raises(OracleError):
        check("Grace", "Whitfield", Decimal("6.0"), date(2026, 5, 20))
