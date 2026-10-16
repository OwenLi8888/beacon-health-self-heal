"""S1 oracle: does a reading match the patient's latest A1c (LOINC 4548-4) in the DB?

Reads the DB directly and never imports from scripts/, so nothing the heal agent edits can change the verdict.
"""
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pymysql
from dotenv import load_dotenv

A1C_LOINC = "4548-4"


class OracleError(Exception):
    """The DB does not give one clear expected answer, so no verdict is possible."""


def connect() -> pymysql.connections.Connection:
    load_dotenv()
    return pymysql.connect(host="127.0.0.1", port=int(os.environ["DB_HOST_PORT"]), user="root",
                           password=os.environ["MYSQL_ROOT_PASSWORD"], database="openemr")


def a1c_rows(conn, first: str, last: str) -> list[tuple[datetime | None, str]]:
    """All A1c rows for the one patient with this exact name, as (date_collected, result)."""
    with conn.cursor() as cur:
        cur.execute("SELECT pid FROM patient_data WHERE fname = %s AND lname = %s", (first, last))
        pids = cur.fetchall()
        if len(pids) != 1:
            raise OracleError(f"expected 1 patient named {first} {last}, found {len(pids)}")
        cur.execute(
            "SELECT rep.date_collected, res.result FROM procedure_result res"
            " JOIN procedure_report rep ON rep.procedure_report_id = res.procedure_report_id"
            " JOIN procedure_order o ON o.procedure_order_id = rep.procedure_order_id"
            " WHERE o.patient_id = %s AND res.result_code = %s",
            (pids[0][0], A1C_LOINC))
        return list(cur.fetchall())


def expected_latest(rows: list[tuple[datetime | None, str]]) -> tuple[Decimal, date]:
    """Latest A1c value and date. Raises instead of guessing on missing, tied or non-numeric data."""
    if not rows:
        raise OracleError("patient has no A1c rows")
    if any(when is None for when, _ in rows):
        raise OracleError("an A1c row has no date_collected")
    rows = sorted(rows, key=lambda r: r[0], reverse=True)
    if len(rows) > 1 and rows[0][0] == rows[1][0]:
        raise OracleError(f"two A1c rows tie on the latest date_collected {rows[0][0]}")
    when, result = rows[0]
    try:
        value = Decimal(result)
    except InvalidOperation:
        raise OracleError(f"latest A1c result {result!r} is not a number") from None
    if not value.is_finite():
        raise OracleError(f"latest A1c result {result!r} is not a number")
    return value, when.date()


def check(first: str, last: str, value: Decimal, day: date) -> tuple[bool, str]:
    """Verdict for a reading of `first last`'s latest A1c."""
    with connect() as conn:
        exp_value, exp_day = expected_latest(a1c_rows(conn, first, last))
    passed = value == exp_value and day == exp_day
    return passed, f"expected {exp_value} on {exp_day}, got {value} on {day}"
