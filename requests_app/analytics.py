"""
Case analytics, reconstructed from the append-only history as of any moment.

Definitions (also in docs/metrics.md, which scripts/verify_analytics.py implements
independently from the raw dataset):

  state at T        to_status of the case's last status event at or before T.
                    Cases created after T, and cases merged at T, are left out.
  open              state is pending or in_progress.
  resolved          state is resolved or closed.
  time to resolve   from created_at to the last "resolved" event at or before T, in hours.
                    A reopened case counts from creation to its final resolution.
  past due          open, and due_at < T.
  resolved late     resolved, and resolution time > due_at.
  breach rate       (resolved late + past due) / (resolved + past due): of the cases whose
                    deadline has been tested, the share that failed it.
  backlog age       T - created_at for open cases, in hours; median and age bands.
"""

from collections import defaultdict
from statistics import median

from django.db import connection

from .models import OPEN_STATUSES, Status

AGE_BANDS = [("under_2_days", 48), ("2_to_7_days", 168), ("7_to_30_days", 720), ("over_30_days", None)]

_SNAPSHOT_SQL = """
SELECT r.id, c.code, w.code, r.created_at, r.due_at, s.to_status, res.created_at
FROM requests_app_servicerequest r
JOIN requests_app_category c ON c.id = r.category_id
JOIN requests_app_ward w ON w.id = r.ward_id
JOIN LATERAL (
    SELECT e.to_status FROM requests_app_caseevent e
    WHERE e.request_id = r.id AND e.kind = 'status' AND e.created_at <= %(as_of)s
    ORDER BY e.created_at DESC, e.id DESC LIMIT 1
) s ON TRUE
LEFT JOIN LATERAL (
    SELECT e.created_at FROM requests_app_caseevent e
    WHERE e.request_id = r.id AND e.kind = 'status' AND e.to_status = 'resolved' AND e.created_at <= %(as_of)s
    ORDER BY e.created_at DESC, e.id DESC LIMIT 1
) res ON TRUE
WHERE r.created_at <= %(as_of)s AND s.to_status <> 'merged' {source_filter}
"""


def _snapshot(as_of, source=None):
    sql = _SNAPSHOT_SQL.format(source_filter="AND r.source = %(source)s" if source else "")
    with connection.cursor() as cur:
        cur.execute(sql, {"as_of": as_of, "source": source})
        return [
            {"id": i, "category": cat, "ward": ward, "created_at": created, "due_at": due,
             "state": state, "resolved_at": resolved}
            for i, cat, ward, created, due, state, resolved in cur.fetchall()
        ]


def _hours(delta):
    return delta.total_seconds() / 3600


def _round(value, places):
    return None if value is None else round(value, places)


def summarise(rows, as_of):
    open_rows = [r for r in rows if r["state"] in OPEN_STATUSES]
    done_rows = [r for r in rows if r["state"] in (Status.RESOLVED, Status.CLOSED)]
    past_due = [r for r in open_rows if r["due_at"] < as_of]
    late = [r for r in done_rows if r["resolved_at"] > r["due_at"]]
    tested = len(done_rows) + len(past_due)
    ages = [_hours(as_of - r["created_at"]) for r in open_rows]

    bands = dict.fromkeys((name for name, _ in AGE_BANDS), 0)
    for age in ages:
        for name, limit in AGE_BANDS:
            if limit is None or age < limit:
                bands[name] += 1
                break

    return {
        "total": len(open_rows) + len(done_rows),
        "open": len(open_rows),
        "resolved": len(done_rows),
        "median_hours_to_resolve": _round(
            median(_hours(r["resolved_at"] - r["created_at"]) for r in done_rows) if done_rows else None, 2
        ),
        "past_due_open": len(past_due),
        "resolved_late": len(late),
        "breach_rate": _round((len(late) + len(past_due)) / tested if tested else None, 4),
        "median_backlog_age_hours": _round(median(ages) if ages else None, 2),
        "backlog_age_bands": bands,
    }


def compute(as_of, source=None):
    rows = _snapshot(as_of, source)
    by_category, by_ward = defaultdict(list), defaultdict(list)
    for r in rows:
        by_category[r["category"]].append(r)
        by_ward[r["ward"]].append(r)
    return {
        "as_of": as_of.isoformat(),
        "source": source or "all",
        "overall": summarise(rows, as_of),
        "by_category": {k: summarise(v, as_of) for k, v in sorted(by_category.items())},
        "by_ward": {k: summarise(v, as_of) for k, v in sorted(by_ward.items())},
    }
