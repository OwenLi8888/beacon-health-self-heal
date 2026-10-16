from datetime import date, time, timedelta

import pytest
from playwright.sync_api import sync_playwright

from oracle.s2_book_appointment import Expected, check, verdict
from scripts.book_appointment import book_appointment

EXP = Expected(pid=2, provider_id=5, catid=5, duration_s=900, day=date(2026, 11, 3), start=time(10, 30))
REQUEST = {"first": "Marcus", "last": "Bell", "provider": "Okoro, Nadia", "type": "Office Visit"}
RETURNED = {"patient": "Bell, Marcus", "provider": "Okoro, Nadia", "type": "Office Visit",
            "date": "2026-11-03", "start": "10:30:00", "duration_min": 15}


def event(**over) -> dict:
    return {"pc_eid": 14, "pc_pid": "2", "pc_aid": "5", "pc_catid": 5, "pc_duration": 900,
            "pc_eventDate": date(2026, 11, 3), "pc_startTime": timedelta(hours=10, minutes=30),
            "pc_recurrtype": 0} | over


def good_diff(**over) -> dict:
    """What a correct booking changes: the appointment, its tracker rows, and session noise."""
    return {
        "openemr_postcalendar_events": ([event()], []),
        "patient_tracker": ([{"id": 1, "eid": 14, "pid": 2}], []),
        "patient_tracker_element": ([{"pt_tracker_id": 1}], []),
        "log": ([{"id": 1}, {"id": 2}], []),
        "sequences": ([{"id": 2}], [{"id": 1}]),
    } | over


def test_accepts_correct_booking():
    assert verdict(good_diff(), EXP, RETURNED, REQUEST) == (True, "one correct appointment, no other changes")


def test_rejects_wrong_patient_booking():
    """Booked for Rosa Delgado (pid 1) when asked for Marcus Bell (pid 2)."""
    diff = good_diff(openemr_postcalendar_events=([event(pc_pid="1")], []),
                     patient_tracker=([{"id": 1, "eid": 14, "pid": 1}], []))
    passed, detail = verdict(diff, EXP, RETURNED, REQUEST)
    assert not passed
    assert "appointment pid: expected 2, got 1" in detail


@pytest.mark.parametrize("diff", [
    good_diff(openemr_postcalendar_events=([event(pc_aid="1")], [])),                   # wrong provider
    good_diff(openemr_postcalendar_events=([event(pc_catid=9)], [])),                   # wrong type
    good_diff(openemr_postcalendar_events=([event(pc_eventDate=date(2026, 11, 4))], [])),  # wrong day
    good_diff(openemr_postcalendar_events=([event(pc_startTime=timedelta(hours=11))], [])),  # wrong time
    good_diff(openemr_postcalendar_events=([event(pc_recurrtype=1)], [])),              # repeating series
    good_diff(openemr_postcalendar_events=([event(), event(pc_eid=15)], [])),           # booked twice
    good_diff(openemr_postcalendar_events=([], [])),                                     # nothing booked
    good_diff(openemr_postcalendar_events=([event()], [event(pc_eid=7)])),              # existing row changed
    good_diff(patient_tracker=([{"id": 1, "eid": 99, "pid": 2}], [])),                   # tracker for another event
    good_diff(patient_data=([{"id": 2}], [{"id": 2}])),                                  # demographics edited
    good_diff(log=([], [{"id": 1}])),                                                    # session row deleted
])
def test_rejects_wrong_db_change(diff):
    assert not verdict(diff, EXP, RETURNED, REQUEST)[0]


@pytest.mark.parametrize("key, value", [
    ("patient", "Delgado, Rosa"), ("provider", "Administrator"), ("start", "10:45:00"), ("duration_min", 30),
])
def test_rejects_wrong_returned_details(key, value):
    assert not verdict(good_diff(), EXP, RETURNED | {key: value}, REQUEST)[0]


# Live UI and DB (make reset first): book for the wrong patient through the real script.

def test_live_wrong_patient_booking_is_caught():
    day, start = date(2026, 11, 3), time(10, 30)
    with sync_playwright() as p:
        appt = book_appointment(p.chromium.launch().new_page(), "Rosa", "Delgado", "Okoro, Nadia",
                                "Office Visit", day, start)
    returned = {"patient": appt.patient, "provider": appt.provider, "type": appt.type,
                "date": appt.date.isoformat(), "start": appt.start.isoformat(), "duration_min": appt.duration_min}
    assert check("Rosa", "Delgado", "Okoro, Nadia", "Office Visit", day, start, returned)[0]
    passed, detail = check("Marcus", "Bell", "Okoro, Nadia", "Office Visit", day, start, returned)
    assert not passed
    assert "appointment pid: expected 2, got 1" in detail
