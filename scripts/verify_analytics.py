"""
Independent check of the dashboard.

Recomputes every analytics figure straight from the raw NYC 311 CSV with pandas and shapely,
without importing Django or touching the database, then compares the result with the app's
own output (`manage.py export_analytics`). If the app's ward routing, deadline arithmetic,
state machine replay or SQL aggregation is wrong, the two disagree.

Deliberately different methods from the app:
  - wards:      shapely point-in-polygon on the GeoJSON file (app: the same check, but with ward shapes loaded from the database)
  - deadlines:  a minute-by-minute working-time grid with cumulative sums
                (app: walks day by day through opening windows)
  - state at T: read directly from created/closed dates (app: replays the event history)

Shared inputs, on purpose: the raw CSV, data/replay_rules.json (the mapping spec),
data/categories.json (the targets), the ward boundary file and the `holidays` package
(Kenyan public holiday dates).

Usage:
  python scripts/verify_analytics.py --as-of 2025-03-15T00:00 --out expected.json
  python scripts/verify_analytics.py --as-of 2025-03-15T00:00 --compare app.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import holidays
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("Africa/Nairobi")

# Opening hours as minute-of-day ranges, by weekday (0 = Monday). Same published hours as the
# app, written out again here rather than imported.
OPENING_MINUTES = {
    "muwasco": {0: (480, 1020), 1: (480, 1020), 2: (480, 1020), 3: (480, 1020), 4: (480, 960), 5: (480, 780)},
    "county": {0: (480, 1020), 1: (480, 1020), 2: (480, 1020), 3: (480, 1020), 4: (480, 1020)},
}


def load_inputs(csv_path):
    rules = json.loads((ROOT / "data" / "replay_rules.json").read_text(encoding="utf-8"))
    cats = json.loads((ROOT / "data" / "categories.json").read_text(encoding="utf-8"))
    wards = json.loads((ROOT / "data" / "boundaries" / "muranga_wards_iebc2012.geojson").read_text(encoding="utf-8"))
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    return rules, cats, wards, df


def map_categories(df, rules):
    exact = {(r["complaint_type"], r["descriptor"]): r["category"] for r in rules["category_map"] if r["descriptor"] != "*"}
    wild = {r["complaint_type"]: r["category"] for r in rules["category_map"] if r["descriptor"] == "*"}
    keys = list(zip(df["complaint_type"], df["descriptor"]))
    return pd.Series([exact.get(k, wild.get(k[0])) for k in keys], index=df.index)


def assign_wards(lon, lat, wards):
    polygons = [(f["properties"]["code"], prep(shape(f["geometry"]))) for f in wards["features"]]
    out = []
    for x, y in zip(lon, lat):
        p = Point(x, y)
        out.append(next((code for code, poly in polygons if poly.contains(p)), None))
    return out


class WorkingGrid:
    """Working seconds as a step function on a one-minute grid."""

    def __init__(self, calendar, start_day, days):
        self.base = datetime.combine(start_day, datetime.min.time(), tzinfo=TZ)
        ke = holidays.Kenya(years=range(start_day.year, start_day.year + 2))
        minutes = np.zeros(days * 1440, dtype=np.int64)
        for d in range(days):
            day = start_day + timedelta(days=d)
            window = OPENING_MINUTES[calendar].get(day.weekday())
            if window and day not in ke:
                minutes[d * 1440 + window[0]: d * 1440 + window[1]] = 1
        self.working = minutes
        self.cum_seconds = np.cumsum(minutes) * 60  # working seconds up to the END of each minute

    def worked_before(self, t):
        offset = (t - self.base).total_seconds()
        i = int(offset // 60)
        before = self.cum_seconds[i - 1] if i > 0 else 0
        return before + self.working[i] * (offset - i * 60)

    def add(self, t, seconds):
        target = self.worked_before(t) + seconds
        j = int(np.searchsorted(self.cum_seconds, target, side="left"))
        start_of_minute_j = self.cum_seconds[j] - 60
        return self.base + timedelta(minutes=j, seconds=float(target - start_of_minute_j))


def compute(as_of, csv_path):
    rules, cats, wards, df = load_inputs(csv_path)
    category_info = {c["code"]: c for c in cats["categories"]}
    calendars = {d["code"]: d["calendar"] for d in cats["departments"]}

    df["category"] = map_categories(df, rules)
    df["state_final"] = df["status"].map(rules["status_map"])
    df = df[df["category"].notna() & df["state_final"].notna()].copy()

    df["created"] = pd.to_datetime(df["created_date"]).dt.tz_localize(TZ)
    df["closed"] = pd.to_datetime(df["closed_date"].replace("", None)).dt.tz_localize(TZ)
    is_closed = df["state_final"] == "closed"
    bad = is_closed & (df["closed"].isna() | (df["closed"] < df["created"]))
    df = df[~bad].copy()

    (sx0, sy0, sx1, sy1) = rules["transform"]["from_bbox"]
    (dx0, dy0, dx1, dy1) = rules["transform"]["to_bbox"]
    lon = dx0 + (df["longitude"].astype(float) - sx0) / (sx1 - sx0) * (dx1 - dx0)
    lat = dy0 + (df["latitude"].astype(float) - sy0) / (sy1 - sy0) * (dy1 - dy0)
    df["ward"] = assign_wards(lon, lat, wards)
    df = df[df["ward"].notna()].copy()

    first_day = df["created"].min().date()
    grids = {cal: WorkingGrid(cal, first_day, 120) for cal in set(calendars.values())}

    def due(row):
        info = category_info[row["category"]]
        seconds = info["sla_hours"] * 3600
        if info["sla_basis"] == "working":
            return grids[calendars[info["department"]]].add(row["created"].to_pydatetime(), seconds)
        return row["created"].to_pydatetime() + timedelta(seconds=seconds)

    df["due"] = df.apply(due, axis=1)

    df = df[df["created"] <= as_of].copy()
    df["done"] = (df["state_final"] == "closed") & (df["closed"] <= as_of)
    df["resolved_at"] = df["closed"].where(df["done"])

    def summarise(g):
        open_g, done_g = g[~g["done"]], g[g["done"]]
        past_due = open_g[open_g["due"] < as_of]
        late = done_g[done_g["resolved_at"] > done_g["due"]]
        tested = len(done_g) + len(past_due)
        hours_to_resolve = [(r - c).total_seconds() / 3600 for r, c in zip(done_g["resolved_at"], done_g["created"])]
        ages = [(as_of - c).total_seconds() / 3600 for c in open_g["created"]]
        bands = {
            "under_2_days": sum(a < 48 for a in ages),
            "2_to_7_days": sum(48 <= a < 168 for a in ages),
            "7_to_30_days": sum(168 <= a < 720 for a in ages),
            "over_30_days": sum(a >= 720 for a in ages),
        }
        return {
            "total": len(g),
            "open": len(open_g),
            "resolved": len(done_g),
            "median_hours_to_resolve": round(float(np.median(hours_to_resolve)), 2) if hours_to_resolve else None,
            "past_due_open": len(past_due),
            "resolved_late": len(late),
            "breach_rate": round((len(late) + len(past_due)) / tested, 4) if tested else None,
            "median_backlog_age_hours": round(float(np.median(ages)), 2) if ages else None,
            "backlog_age_bands": {k: int(v) for k, v in bands.items()},
        }

    return {
        "as_of": as_of.isoformat(),
        "source": "replay",
        "overall": summarise(df),
        "by_category": {k: summarise(g) for k, g in sorted(df.groupby("category"))},
        "by_ward": {k: summarise(g) for k, g in sorted(df.groupby("ward"))},
    }


def diff(expected, actual, path=""):
    problems = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in actual:
                problems.append(f"{path}/{key}: missing from app output")
            elif key not in expected:
                problems.append(f"{path}/{key}: app has it, independent computation does not")
            else:
                problems += diff(expected[key], actual[key], f"{path}/{key}")
    elif expected != actual:
        problems.append(f"{path}: expected {expected!r}, app reported {actual!r}")
    return problems


def count_leaves(d):
    return sum(count_leaves(v) for v in d.values()) if isinstance(d, dict) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--csv", default=str(ROOT / "data" / "raw" / "nyc311_2025-03-01_to_2025-03-07.csv"))
    parser.add_argument("--out")
    parser.add_argument("--compare", help="JSON written by `manage.py export_analytics --source replay`")
    args = parser.parse_args()

    as_of = datetime.fromisoformat(args.as_of).replace(tzinfo=TZ)
    expected = compute(as_of, args.csv)
    if args.out:
        Path(args.out).write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.compare:
        actual = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        problems = diff(expected, actual)
        if problems:
            print(f"MISMATCH: {len(problems)} figure(s) differ")
            print("\n".join(problems[:50]))
            sys.exit(1)
        print(f"MATCH: all {count_leaves(expected)} figures identical "
              f"({expected['overall']['total']} cases, {len(expected['by_ward'])} wards, "
              f"{len(expected['by_category'])} categories, as of {expected['as_of']})")


if __name__ == "__main__":
    main()
