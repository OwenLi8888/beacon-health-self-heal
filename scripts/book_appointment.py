"""S2: book an appointment for a patient with a given provider, type, date and time.

Usage: uv run python -m scripts.book_appointment --first Marcus --last Bell \
         --provider "Okoro, Nadia" --type "Office Visit" --date 2026-11-03 --time 10:30
"""
import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time

from playwright.sync_api import FrameLocator, Page, sync_playwright

from scripts.common import ValueNotFound, login, step, writes_data
from scripts.read_a1c import open_chart, search_patient


@dataclass(frozen=True)
class Appointment:
    patient: str  # "Last, First", as the dialog shows it
    provider: str
    type: str
    date: date
    start: time
    duration_min: int


@step
def open_calendar(page: Page) -> FrameLocator:
    # The menu also holds a hidden "Calendar" entry inside a submenu.
    page.get_by_role("navigation").get_by_text("Calendar", exact=True).filter(visible=True).click()
    cal = page.frame_locator("iframe[name='cal']")
    cal.get_by_role("link", name="Day", exact=True).wait_for()
    return cal


@step
def open_new_appointment(page: Page, cal: FrameLocator) -> FrameLocator:
    """'+' opens the add-event dialog, prefilled with the patient whose chart is open."""
    cal.get_by_role("link", name="+", exact=True).click()
    dialog = page.frame_locator("iframe[src*='add_edit_event.php']")
    dialog.get_by_role("button", name="Save").wait_for()
    return dialog


@step
def fill_appointment(dialog: FrameLocator, first: str, last: str, provider: str, type_: str,
                     day: date, start: time) -> Appointment:
    """Fill the form, then read every field back so the result is what the form holds, not what we asked for."""
    patient = dialog.get_by_label("Patient:").input_value()
    if patient != f"{last}, {first}":
        raise ValueNotFound(f"dialog patient is {patient!r}, expected '{last}, {first}'")
    dialog.get_by_label("Category:").select_option(label=type_)
    dialog.get_by_label("Provider:").select_option(label=provider)
    dialog.get_by_label("Date:").fill(day.isoformat())
    # Hour and minute are two unlabelled boxes that share the title "Event start time".
    hour, minute = dialog.get_by_role("textbox", name="Event start time").all()
    hour.fill(str(start.hour))
    minute.fill(f"{start.minute:02d}")

    def selected(label: str) -> str:
        return dialog.get_by_label(label).locator("option:checked").inner_text().strip()

    duration = dialog.get_by_role("textbox", name="Event duration in minutes").input_value()
    if not re.fullmatch(r"[1-9]\d*", duration):
        raise ValueNotFound(f"cannot parse duration {duration!r}")
    try:
        when = datetime.strptime(f"{dialog.get_by_label('Date:').input_value()} "
                                 f"{hour.input_value()}:{minute.input_value()}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueNotFound("cannot parse the dialog's date and time") from None
    return Appointment(patient, selected("Provider:"), selected("Category:"), when.date(), when.time(),
                       int(duration))


@step
@writes_data
def save_appointment(page: Page, dialog: FrameLocator) -> None:
    """The dialog closes only when the save went through. Any confirm (provider unavailable,
    slot taken, holiday) is dismissed by Playwright, so the dialog stays and this step fails."""
    dialog.get_by_role("button", name="Save").click()
    page.locator("iframe[src*='add_edit_event.php']").wait_for(state="detached")


def book_appointment(page: Page, first: str, last: str, provider: str, type_: str,
                     day: date, start: time) -> Appointment:
    login(page)
    search_patient(page, first, last)
    open_chart(page, first, last)
    cal = open_calendar(page)
    dialog = open_new_appointment(page, cal)
    appt = fill_appointment(dialog, first, last, provider, type_, day, start)
    save_appointment(page, dialog)
    return appt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", required=True)
    ap.add_argument("--last", required=True)
    ap.add_argument("--provider", required=True, help='as listed in the dialog, e.g. "Okoro, Nadia"')
    ap.add_argument("--type", required=True, help='appointment category, e.g. "Office Visit"')
    ap.add_argument("--date", required=True, type=date.fromisoformat)
    ap.add_argument("--time", required=True, type=time.fromisoformat)
    args = ap.parse_args()
    with sync_playwright() as p:
        appt = book_appointment(p.chromium.launch().new_page(), args.first, args.last, args.provider,
                                args.type, args.date, args.time)
    print(json.dumps(asdict(appt), default=str))


if __name__ == "__main__":
    main()
