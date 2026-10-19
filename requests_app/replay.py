"""Shared rules for replaying the NYC 311 sample. See data/replay_rules.json and docs/replay.md."""

import csv
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings

from .deadlines import NAIROBI

DATA_DIR = Path(settings.BASE_DIR) / "data"
RULES_FILE = DATA_DIR / "replay_rules.json"
DEFAULT_CSV = DATA_DIR / "raw" / "nyc311_2025-03-01_to_2025-03-07.csv"


def load_rules():
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def category_for(rules, complaint_type, descriptor):
    wildcard = None
    for rule in rules["category_map"]:
        if rule["complaint_type"] != complaint_type:
            continue
        if rule["descriptor"] == descriptor:
            return rule["category"]
        if rule["descriptor"] == "*":
            wildcard = rule["category"]
    return wildcard


def transform(rules, longitude, latitude):
    (sx0, sy0, sx1, sy1) = rules["transform"]["from_bbox"]
    (dx0, dy0, dx1, dy1) = rules["transform"]["to_bbox"]
    x = dx0 + (longitude - sx0) / (sx1 - sx0) * (dx1 - dx0)
    y = dy0 + (latitude - sy0) / (sy1 - sy0) * (dy1 - dy0)
    return x, y


def parse_local(value):
    return datetime.fromisoformat(value).replace(tzinfo=NAIROBI) if value else None


def read_rows(path=DEFAULT_CSV):
    with open(path, encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)
