"""
1. Database guards, so the rules hold even for code that bypasses services.py:
   - a status change that isn't in statemachine.TRANSITIONS is rejected;
   - a new report must start as pending;
   - case history (CaseEvent) can be appended to but never updated or deleted.
2. Departments and categories from data/categories.json.
"""

import json
from pathlib import Path

from django.db import migrations

from requests_app.statemachine import APPEND_ONLY_SQL, trigger_sql

CATEGORIES_FILE = Path(__file__).resolve().parents[2] / "data" / "categories.json"


def load_reference_data(apps, schema_editor):
    Department = apps.get_model("requests_app", "Department")
    Category = apps.get_model("requests_app", "Category")
    data = json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
    departments = {}
    for d in data["departments"]:
        departments[d["code"]], _ = Department.objects.update_or_create(
            code=d["code"], defaults={"name": d["name"], "calendar": d["calendar"]}
        )
    for position, c in enumerate(data["categories"]):
        Category.objects.update_or_create(
            code=c["code"],
            defaults={
                "name": c["name"], "description": c["description"], "department": departments[c["department"]],
                "sla_hours": c["sla_hours"], "sla_basis": c["sla_basis"], "sla_is_assumed": c["assumed"],
                "sla_source": c["sla_source"], "position": position,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("requests_app", "0001_initial")]

    operations = [
        migrations.RunSQL(
            trigger_sql(),
            reverse_sql="""
                DROP TRIGGER IF EXISTS servicerequest_status_transition ON requests_app_servicerequest;
                DROP TRIGGER IF EXISTS servicerequest_starts_pending ON requests_app_servicerequest;
                DROP FUNCTION IF EXISTS requests_app_check_status_transition();
                DROP FUNCTION IF EXISTS requests_app_new_request_is_pending();
            """,
        ),
        migrations.RunSQL(
            APPEND_ONLY_SQL,
            reverse_sql="""
                DROP TRIGGER IF EXISTS caseevent_append_only ON requests_app_caseevent;
                DROP FUNCTION IF EXISTS requests_app_case_event_append_only();
            """,
        ),
        migrations.RunPython(load_reference_data, migrations.RunPython.noop),
    ]
