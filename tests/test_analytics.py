"""Small hand-checked scenario for the analytics definitions in docs/metrics.md. The full
dataset is checked independently by scripts/verify_analytics.py in CI."""

from datetime import datetime, timedelta

import pytest

from requests_app import analytics, services
from requests_app.deadlines import NAIROBI
from requests_app.models import Status

T0 = datetime(2025, 11, 3, 9, 0, tzinfo=NAIROBI)  # a Monday, no holiday


@pytest.fixture
def scenario(make_request, water_officer, citizen):
    """Three burst-main reports (25 clock-hour target), made at T0:
       A resolved after 10 h (on time), B resolved after 30 h (late), C still open."""
    a = make_request("pipe_burst", created_at=T0)
    b = make_request("pipe_burst", created_at=T0)
    c = make_request("pipe_burst", created_at=T0)
    for req, hours in [(a, 10), (b, 30)]:
        services.transition(req, Status.IN_PROGRESS, water_officer, at=T0 + timedelta(hours=1))
        services.transition(req, Status.RESOLVED, water_officer, note="Fixed", at=T0 + timedelta(hours=hours))
    services.transition(c, Status.IN_PROGRESS, water_officer, at=T0 + timedelta(hours=2))
    return a, b, c


@pytest.mark.django_db
def test_snapshot_after_everything(scenario):
    m = analytics.compute(T0 + timedelta(hours=48))["overall"]
    assert (m["open"], m["resolved"]) == (1, 2)
    assert m["median_hours_to_resolve"] == 20.0  # median of 10 and 30
    assert (m["resolved_late"], m["past_due_open"]) == (1, 1)  # B late; C open past 25 h
    assert m["breach_rate"] == round(2 / 3, 4)
    assert m["median_backlog_age_hours"] == 48.0
    assert m["backlog_age_bands"]["2_to_7_days"] == 1


@pytest.mark.django_db
def test_snapshot_in_the_past_is_reconstructed_from_history(scenario):
    m = analytics.compute(T0 + timedelta(hours=12))["overall"]
    # At T0+12h only A had been resolved; B and C were still open and not yet due.
    assert (m["open"], m["resolved"]) == (2, 1)
    assert m["median_hours_to_resolve"] == 10.0
    assert m["past_due_open"] == 0 and m["breach_rate"] == 0.0


@pytest.mark.django_db
def test_before_anything_was_reported(scenario):
    m = analytics.compute(T0 - timedelta(minutes=1))["overall"]
    assert m["total"] == 0 and m["median_hours_to_resolve"] is None and m["breach_rate"] is None


@pytest.mark.django_db
def test_reopened_case_counts_to_final_resolution(make_request, water_officer, citizen):
    req = make_request("pipe_burst", created_at=T0)
    services.transition(req, Status.IN_PROGRESS, water_officer, at=T0)
    services.transition(req, Status.RESOLVED, water_officer, note="Fixed", at=T0 + timedelta(hours=5))
    services.transition(req, Status.IN_PROGRESS, citizen, note="Still broken", at=T0 + timedelta(hours=6))
    services.transition(req, Status.RESOLVED, water_officer, note="Really fixed", at=T0 + timedelta(hours=20))
    assert analytics.compute(T0 + timedelta(hours=5, minutes=30))["overall"]["resolved"] == 1
    assert analytics.compute(T0 + timedelta(hours=7))["overall"]["open"] == 1
    assert analytics.compute(T0 + timedelta(hours=21))["overall"]["median_hours_to_resolve"] == 20.0


@pytest.mark.django_db
def test_merged_duplicates_are_not_double_counted(make_request, water_officer):
    original = make_request("pipe_burst", created_at=T0)
    duplicate = make_request("pipe_burst", created_at=T0 + timedelta(minutes=5))
    services.transition(duplicate, Status.MERGED, water_officer, note="Same", merge_into=original,
                        at=T0 + timedelta(hours=1))
    assert analytics.compute(T0 + timedelta(minutes=30))["overall"]["open"] == 2
    assert analytics.compute(T0 + timedelta(hours=2))["overall"]["open"] == 1


@pytest.mark.django_db
def test_breakdowns_add_up(scenario):
    result = analytics.compute(T0 + timedelta(hours=48))
    for key in ("open", "resolved", "past_due_open", "resolved_late"):
        assert sum(m[key] for m in result["by_ward"].values()) == result["overall"][key]
        assert sum(m[key] for m in result["by_category"].values()) == result["overall"][key]
