"""Row-level diff of the live `openemr` DB against `openemr_snap`, the clean copy made by `make snapshot`.

Rows are compared whole with EXCEPT ALL in both directions, so a changed row shows up as one
added plus one removed. Two kinds of column are left out, because page views change them on their own:
`uuid` (OpenEMR backfills it lazily) and ON UPDATE CURRENT_TIMESTAMP columns (MariaDB bumps them on
that backfill). Any other column that changes in the same row still shows the row as changed.
"""
import pymysql

LIVE, SNAP = "openemr", "openemr_snap"
IGNORED_COLUMNS = {"uuid"}


class SnapshotMismatch(Exception):
    """The live DB and the snapshot don't have the same tables and columns, so rows can't be compared."""


def _columns(cur, schema: str) -> dict[str, list[str]]:
    """Compared columns per base table."""
    cur.execute("SELECT c.TABLE_NAME, c.COLUMN_NAME, c.EXTRA FROM information_schema.COLUMNS c"
                " JOIN information_schema.TABLES t"
                "   ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME"
                " WHERE c.TABLE_SCHEMA = %s AND t.TABLE_TYPE = 'BASE TABLE'"
                " ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION", (schema,))
    cols: dict[str, list[str]] = {}
    for table, col, extra in cur.fetchall():
        cols.setdefault(table, [])
        if col not in IGNORED_COLUMNS and not extra.lower().startswith("on update"):
            cols[table].append(col)
    return cols


def diff(conn: pymysql.connections.Connection) -> dict[str, tuple[list[dict], list[dict]]]:
    """{table: (added_rows, removed_rows)} for every table whose rows differ from the snapshot."""
    with conn.cursor() as cur:
        live, snap = _columns(cur, LIVE), _columns(cur, SNAP)
    if not snap:
        raise SnapshotMismatch(f"schema {SNAP} is missing or empty; run make snapshot on a clean DB")
    if live != snap:
        tables = sorted(t for t in live.keys() | snap.keys() if live.get(t) != snap.get(t))
        raise SnapshotMismatch(f"tables or columns differ from the snapshot: {tables}")

    changes = {}
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        for table, cols in live.items():
            select = ", ".join(f"`{c}`" for c in cols)
            rows = []
            for a, b in ((LIVE, SNAP), (SNAP, LIVE)):
                cur.execute(f"SELECT {select} FROM `{a}`.`{table}` EXCEPT ALL SELECT {select} FROM `{b}`.`{table}`")
                rows.append(list(cur.fetchall()))
            if rows[0] or rows[1]:
                changes[table] = (rows[0], rows[1])
    return changes
