"""
Replay the NYC 311 sample through the real application: every row becomes a report created by
services.create_request() (ward lookup, duplicate check, charter deadline) and moves
through services.transition() (state machine, history, database triggers). Idempotent: rows
already replayed are skipped, so it is safe to run on every start.
"""

import json
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from requests_app import replay, services
from requests_app.geo import make_point
from requests_app.models import Category, ServiceRequest, Status
from requests_app.management.commands.seed_demo import REPLAY_ACCOUNT


class Command(BaseCommand):
    help = "Replay the NYC 311 sample into Murang'a (see docs/replay.md)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(replay.DEFAULT_CSV))

    def handle(self, *args, file, **options):
        rules = replay.load_rules()
        citizen, _ = User.objects.get_or_create(
            phone=REPLAY_ACCOUNT, defaults={"full_name": "NYC 311 replay (dataset)", "is_active": False}
        )
        categories = {c.code: c for c in Category.objects.select_related("department")}
        done = set(ServiceRequest.objects.filter(source=ServiceRequest.Source.REPLAY).values_list("external_ref", flat=True))
        outcome = Counter()

        for row in replay.read_rows(file):
            if row["unique_key"] in done:
                outcome["already_loaded"] += 1
                continue
            outcome[self._replay_row(rules, row, citizen, categories)] += 1

        self.stdout.write(json.dumps(dict(sorted(outcome.items()))))

    @transaction.atomic
    def _replay_row(self, rules, row, citizen, categories):
        code = replay.category_for(rules, row["complaint_type"], row["descriptor"])
        if code is None:
            return "unmapped"
        status = rules["status_map"].get(row["status"])
        if status is None:
            return "unknown_status"
        created = replay.parse_local(row["created_date"])
        closed = replay.parse_local(row["closed_date"]) if status == Status.CLOSED else None
        if status == Status.CLOSED and (closed is None or closed < created):
            return "bad_dates"
        lon, lat = replay.transform(rules, float(row["longitude"]), float(row["latitude"]))
        try:
            req = services.create_request(
                citizen=citizen, category=categories[code], point=make_point(lat, lon),
                description=f"{row['complaint_type']}: {row['descriptor']} (NYC 311 #{row['unique_key']})",
                source=ServiceRequest.Source.REPLAY, created_at=created, external_ref=row["unique_key"],
            )
        except services.OutsideCounty:
            return "outside_county"
        if status in (Status.IN_PROGRESS, Status.CLOSED):
            services.transition(req, Status.IN_PROGRESS, actor=None, at=created)
        if status == Status.CLOSED:
            services.transition(req, Status.RESOLVED, actor=None, at=closed, note="Closed in source dataset.")
            services.transition(req, Status.CLOSED, actor=None, at=closed, note="Closed in source dataset.")
        return "loaded"
