import json
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from requests_app import analytics


class Command(BaseCommand):
    help = "Print the dashboard figures as JSON, exactly as the analytics page computes them."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", required=True, help="Local Nairobi time, e.g. 2025-03-15T00:00")
        parser.add_argument("--source", choices=["web", "open311", "replay"])
        parser.add_argument("--out", help="Write to this file instead of stdout")

    def handle(self, *args, as_of, source, out, **options):
        moment = timezone.make_aware(datetime.fromisoformat(as_of))
        text = json.dumps(analytics.compute(moment, source=source), indent=2, sort_keys=True)
        if out:
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        else:
            self.stdout.write(text)
