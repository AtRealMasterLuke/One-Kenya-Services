# Metric definitions

Every figure on the analytics page follows these definitions. Two separate implementations
compute them:

* the app (`requests_app/analytics.py`): SQL over the append-only case history;
* the independent checker (`scripts/verify_analytics.py`): pandas over the raw CSV, without
  Django or the database.

CI runs both at three snapshot times and fails if any figure differs.

All times are Africa/Nairobi. **T** is the "as of" moment chosen on the page.

| Term | Definition |
|---|---|
| **State at T** | The `to_status` of the case's last status event at or before T. Cases created after T are left out. Cases whose state at T is `merged` are left out, so a duplicate is never counted twice. |
| **Open** | State at T is `pending` or `in_progress`. |
| **Resolved** | State at T is `resolved` or `closed`. |
| **Time to resolve** | From `created_at` to the last `resolved` event at or before T, in hours. A reopened case counts from creation to its *final* resolution, because the earlier "fix" didn't hold. |
| **Median time to resolve** | Median of time to resolve over resolved cases, rounded to 2 decimals. |
| **Deadline** (`due_at`) | Fixed when the report is made: `created_at` plus the category's target. Targets are in clock hours or working hours (see `requests_app/deadlines.py`); working hours follow MUWASCO's or the county's published hours and skip Kenyan public holidays. |
| **Past due** | Open at T, and `due_at` < T. |
| **Resolved late** | Resolved at T, and time of resolution > `due_at`. |
| **Breach rate** | (resolved late + past due) ÷ (resolved + past due). Of the cases whose deadline has actually been put to the test, the share that failed it. Cases still open and not yet due are excluded, since they haven't passed or failed yet. Rounded to 4 decimals. |
| **Backlog age** | T − `created_at` for open cases, in hours. The page shows the median and four bands: under 2 days, 2–7 days, 7–30 days, over 30 days. |

## Why these and not just "open vs resolved"

A count of open against resolved cases rewards closing tickets, not fixing things, and it
hides long waits. Each extra figure answers a question a county manager has to answer:

* *How long do people wait?* Median time to resolve. (A median, because a few cases open for
  months would make a mean meaningless.)
* *Are we keeping the promises in the charter?* Breach rate.
* *Is the backlog going stale?* Backlog age bands.
* *Where?* Every figure is broken down by ward and by problem type.
