"""S2 oracle: did the run book exactly one correct appointment and change nothing else?

Golden-master diff of the whole DB against the clean snapshot (oracle/db_diff.py). Reads the DB
directly and never imports from scripts/, so nothing the heal agent edits can change the verdict.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from oracle.db_diff import diff
from oracle.s1_read_a1c import OracleError, connect

# Tables any logged-in UI session writes to, found by diffing a read-only S1 run against the
# snapshot: audit log, session and login tracking, lazy uuid/contact backfill, saved UI settings,
# recent-patients list, clinical reminder log. They may gain rows; existing rows must not change.
SESSION_TABLES = {"log", "log_comment_encrypt", "session_tracker", "ip_tracking", "globals",
                  "uuid_registry", "contact", "user_settings", "recent_patients", "clinical_rules_log"}
# ID counter, updated in place whenever OpenEMR hands out a new id.
COUNTER_TABLES = {"sequences"}


@dataclass(frozen=True)
class Expected:
    pid: int
    provider_id: int
    catid: int
    duration_s: int
    day: date
    start: time


def expected(conn, first: str, last: str, provider: str, type_: str, day: date, start: time) -> Expected:
    """Resolve names to IDs. `provider` is the dialog's label: "Last, First", or "Last" if no first name."""
    plast, _, pfirst = provider.partition(", ")
    with conn.cursor() as cur:
        cur.execute("SELECT pid FROM patient_data WHERE fname = %s AND lname = %s", (first, last))
        pids = cur.fetchall()
        cur.execute("SELECT id FROM users WHERE lname = %s AND fname = %s AND authorized = 1 AND active = 1",
                    (plast, pfirst))
        providers = cur.fetchall()
        # pc_cattype 0 = patient appointment (not In/Out Of Office, holidays or group events).
        cur.execute("SELECT pc_catid, pc_duration FROM openemr_postcalendar_categories"
                    " WHERE pc_catname = %s AND pc_cattype = 0 AND pc_active = 1", (type_,))
        cats = cur.fetchall()
    for what, rows in (("patient", pids), ("provider", providers), ("appointment type", cats)):
        if len(rows) != 1:
            raise OracleError(f"expected 1 {what} matching the request, found {len(rows)}")
    return Expected(int(pids[0][0]), int(providers[0][0]), int(cats[0][0]), int(cats[0][1]), day, start)


def _as_time(v) -> time | None:
    """PyMySQL returns TIME columns as timedelta."""
    return (datetime.min + v).time() if isinstance(v, timedelta) else v


def verdict(changes: dict[str, tuple[list[dict], list[dict]]], exp: Expected, returned: dict,
            request: dict) -> tuple[bool, str]:
    """Judge a DB diff and the script's returned details. Pure, so unit tests can feed it diffs."""
    problems = []
    changes = dict(changes)

    def take(table: str) -> tuple[list[dict], list[dict]]:
        return changes.pop(table, ([], []))

    added, removed = take("openemr_postcalendar_events")
    if removed or len(added) != 1:
        problems.append(f"appointments: expected +1 -0, got +{len(added)} -{len(removed)}")
        event = None
    else:
        event = added[0]
        # pc_pid and pc_aid are text columns: compare as text so a malformed row fails, not crashes.
        got = {"pid": str(event["pc_pid"]), "provider_id": str(event["pc_aid"]), "catid": event["pc_catid"],
               "duration_s": event["pc_duration"], "day": event["pc_eventDate"],
               "start": _as_time(event["pc_startTime"]), "repeats": event["pc_recurrtype"]}
        want = vars(exp) | {"pid": str(exp.pid), "provider_id": str(exp.provider_id), "repeats": 0}
        problems += [f"appointment {k}: expected {want[k]}, got {got[k]}" for k in want if got[k] != want[k]]

    tracked, untracked = take("patient_tracker")
    if untracked or len(tracked) != 1:
        problems.append(f"patient_tracker: expected +1 -0, got +{len(tracked)} -{len(untracked)}")
    elif event and (tracked[0]["eid"], str(tracked[0]["pid"])) != (event["pc_eid"], str(exp.pid)):
        problems.append(f"patient_tracker row is for eid {tracked[0]['eid']} pid {tracked[0]['pid']}, "
                        f"not the new appointment")
    elements, gone = take("patient_tracker_element")
    if gone or len(elements) != 1:
        problems.append(f"patient_tracker_element: expected +1 -0, got +{len(elements)} -{len(gone)}")
    elif len(tracked) == 1 and elements[0]["pt_tracker_id"] != tracked[0]["id"]:
        problems.append("patient_tracker_element does not belong to the new tracker row")

    for table, (plus, minus) in sorted(changes.items()):
        if table in COUNTER_TABLES or (table in SESSION_TABLES and not minus):
            continue
        problems.append(f"unexpected change in {table}: +{len(plus)} -{len(minus)}")

    # The script's return value must describe the same booking.
    want_returned = {"patient": f"{request['last']}, {request['first']}", "provider": request["provider"],
                     "type": request["type"], "date": exp.day.isoformat(), "start": exp.start.isoformat(),
                     "duration_min": exp.duration_s // 60}
    problems += [f"returned {k}: expected {v!r}, got {returned.get(k)!r}"
                 for k, v in want_returned.items() if returned.get(k) != v]
    return not problems, "; ".join(problems) or "one correct appointment, no other changes"


def check(first: str, last: str, provider: str, type_: str, day: date, start: time,
          returned: dict) -> tuple[bool, str]:
    """Verdict for a run asked to book `first last` with `provider`, `type_`, on `day` at `start`."""
    request = {"first": first, "last": last, "provider": provider, "type": type_}
    with connect() as conn:
        exp = expected(conn, first, last, provider, type_, day, start)
        return verdict(diff(conn), exp, returned, request)
