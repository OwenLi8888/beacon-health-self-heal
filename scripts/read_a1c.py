"""S1: read a patient's most recent Hemoglobin A1c (LOINC 4548-4) value and date from the chart.

Usage: uv run python -m scripts.read_a1c --first Rosa --last Delgado --dob 1961-03-14
"""
import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from playwright.sync_api import FrameLocator, Page, sync_playwright

from scripts.common import AmbiguousValue, ValueNotFound, login, step

A1C_LOINC = "4548-4"


@dataclass(frozen=True)
class A1cReading:
    value: Decimal
    date: date


@step
def search_patient(page: Page, first: str, last: str, dob: str) -> None:
    """Search by last name, then open the one finder row named exactly `last, first`."""
    box = page.get_by_placeholder("Search by any demographics")
    box.fill(last)
    box.press("Enter")
    finder = page.frame_locator("iframe[name='fin']")
    finder.get_by_role("status").filter(has_text=re.compile(r"^Showing [1-9]")).wait_for()
    matches = finder.get_by_role("link", name=f"{last}, {first}", exact=True)
    if matches.count() == 0:
        raise ValueNotFound(f"no patient named {first} {last} in search results")
    if matches.count() > 1:
        raise AmbiguousValue(f"{matches.count()} patients named {first} {last}")
    matches.click()


@step
def open_chart(page: Page, first: str, last: str) -> FrameLocator:
    """Wait until the chart header names this patient; return the chart iframe."""
    page.get_by_role("heading", name=re.compile(rf"^{re.escape(first)} {re.escape(last)} \(")).wait_for()
    return page.frame_locator("iframe[name='pat']")


@step
def open_lab_results(chart: FrameLocator) -> None:
    """Open the full lab data page from the chart's Labs card."""
    link = chart.get_by_role("link", name="Click here to view and graph all labdata.")
    none = chart.get_by_text("No lab data documented.")
    link.or_(none).wait_for()
    if none.count():
        raise ValueNotFound("chart says: No lab data documented.")
    link.click()
    chart.get_by_role("heading", name="Labs", level=2).wait_for()


@step
def read_latest_a1c(chart: FrameLocator) -> A1cReading:
    """List A1c results (newest first) and parse the top row."""
    # The item checkboxes and output radios have no labels; name/value are the only handles.
    a1c_box = chart.locator(f"input[name='value_code[]'][value='{A1C_LOINC}']")
    if a1c_box.count() == 0:
        raise ValueNotFound(f"no {A1C_LOINC} (A1c) results for this patient")
    a1c_box.check()
    chart.locator("input[name='mode'][value='list']").check()
    chart.get_by_role("button", name="Submit").click()

    table = chart.get_by_role("table").filter(has=chart.get_by_role("columnheader", name="Result", exact=True))
    table.wait_for()
    # Cells are padded with &nbsp;, which str.strip() removes.
    headers = [h.strip() for h in table.get_by_role("columnheader").all_inner_texts()]
    rows = []
    for row in table.get_by_role("row").all():
        cells = [c.strip() for c in row.get_by_role("cell").all_inner_texts()]
        if len(cells) <= 1:  # spacer and "Plot item" rows
            continue
        if len(cells) != len(headers):
            raise ValueNotFound(f"A1c row has {len(cells)} cells, header has {len(headers)}: {cells}")
        rows.append(cells)
    if not rows:
        raise ValueNotFound("A1c result table has no rows")
    top = dict(zip(headers, rows[0]))
    if len(rows) > 1 and dict(zip(headers, rows[1]))["Date"] == top["Date"]:
        raise AmbiguousValue(f"two A1c results share the latest date {top['Date']}")

    # Abnormal results carry a "+" flag in the cell, e.g. "+ 6.9".
    value = re.fullmatch(r"\+?\s*(\d+(?:\.\d+)?)", top["Result"])
    if not value:
        raise ValueNotFound(f"cannot parse A1c value from {top['Result']!r}")
    try:
        when = datetime.strptime(top["Date"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueNotFound(f"cannot parse A1c date from {top['Date']!r}") from None
    return A1cReading(Decimal(value[1]), when.date())


def read_a1c(page: Page, first: str, last: str, dob: str) -> A1cReading:
    datetime.strptime(dob, "%Y-%m-%d")  # the case's date of birth; raises if it isn't YYYY-MM-DD
    login(page)
    search_patient(page, first, last, dob)
    chart = open_chart(page, first, last)
    open_lab_results(chart)
    return read_latest_a1c(chart)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", required=True)
    ap.add_argument("--last", required=True)
    ap.add_argument("--dob", required=True, help="date of birth, YYYY-MM-DD")
    args = ap.parse_args()
    with sync_playwright() as p:
        reading = read_a1c(p.chromium.launch().new_page(), args.first, args.last, args.dob)
    print(json.dumps({"first": args.first, "last": args.last, "value": str(reading.value),
                      "date": reading.date.isoformat()}))


if __name__ == "__main__":
    main()
