"""
The case lifecycle, tested three ways:

1. Property-based (Hypothesis stateful testing): random sequences of actions by random
   actors against the real service layer and database. After every step, invariants
   about the case and its history must hold, and every refused action must leave no trace.
2. The database triggers, exercised directly with SQL, so the rules hold even for code
   that bypasses services.py.
3. A few named scenarios that read as documentation.
"""

import itertools

import pytest
from django.db import IntegrityError, InternalError, connection, transaction
from django.db.utils import DatabaseError
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule, run_state_machine_as_test

from accounts.models import Role, User
from requests_app import services, statemachine
from requests_app.models import CaseEvent, Category, Department, ServiceRequest, Status, Ward
from requests_app.statemachine import TRANSITIONS, TransitionError

ALL_STATUSES = list(Status)
_seq = itertools.count(1000)


def _user(role, department=None):
    return User.objects.create_user(
        phone=f"+2541{next(_seq):08d}", password="x", full_name=role, role=role, department=department
    )


# What each actor is to a water-leak case, stated independently of statemachine.role_of().
EXPECTED_ROLES = {
    "owner": statemachine.OWNER,
    "stranger": None,
    "water_officer": statemachine.OFFICER,
    "roads_officer": None,  # officers only act on their own department's cases
    "admin": statemachine.ADMIN,
    "system": statemachine.SYSTEM,
}


class CaseLifecycle(RuleBasedStateMachine):
    """One water-leak case; actors: its owner, a stranger, a water officer, a roads officer,
    an admin, and the system. Each rule tries one move and records what should happen."""

    @initialize()
    def setup(self):
        water = Department.objects.get(code="water")
        roads = Department.objects.get(code="roads")
        self.actors = {
            "owner": _user(Role.CITIZEN),
            "stranger": _user(Role.CITIZEN),
            "water_officer": _user(Role.OFFICER, water),
            "roads_officer": _user(Role.OFFICER, roads),
            "admin": _user(Role.ADMIN),
            "system": None,
        }
        ward = Ward.objects.get(name="Township")
        category = Category.objects.get(code="water_leak")
        self.req = services.create_request(
            citizen=self.actors["owner"], category=category, point=ward.shape.representative_point(),
            description="Property test case",
        )
        self.target = services.create_request(
            citizen=self.actors["stranger"], category=category, point=ward.shape.representative_point(),
            description="Merge target",
        )
        self.expected_status = Status.PENDING
        self.status_events = 1  # the "reported" event
        self.ever_resolved = False

    @rule(
        to=st.sampled_from(ALL_STATUSES),
        who=st.sampled_from(["owner", "stranger", "water_officer", "roads_officer", "admin", "system"]),
        with_note=st.booleans(),
    )
    def attempt(self, to, who, with_note):
        actor = self.actors[who]
        frm = self.expected_status
        role = EXPECTED_ROLES[who]  # written out here, not taken from the code under test
        note = "because" if with_note else ""
        should_succeed = (
            (frm, to) in TRANSITIONS
            and role in TRANSITIONS[(frm, to)]
            and (with_note or (frm, to) not in statemachine.NOTE_REQUIRED)
            and (to != Status.MERGED or self.target.is_open)
        )
        events_before = CaseEvent.objects.filter(request=self.req).count()
        try:
            services.transition(self.req, to, actor, note=note, merge_into=self.target)
        except TransitionError:
            assert not should_succeed, f"{who} ({role}) was refused {frm}->{to} but it should be allowed"
            assert CaseEvent.objects.filter(request=self.req).count() == events_before, "refused move left history"
            return
        assert should_succeed, f"{who} ({role}) managed {frm}->{to}, which the rules forbid"
        self.expected_status = to
        self.status_events += 1
        self.ever_resolved |= to == Status.RESOLVED

    @invariant()
    def status_matches_model(self):
        self.req.refresh_from_db()
        assert self.req.status == self.expected_status

    @invariant()
    def history_explains_status(self):
        events = list(self.req.events.filter(kind="status").order_by("created_at", "id"))
        assert len(events) == self.status_events
        assert events[0].from_status == "" and events[0].to_status == Status.PENDING
        for before, after in zip(events, events[1:]):
            assert after.from_status == before.to_status, "history has a gap"
            assert (Status(after.from_status), Status(after.to_status)) in TRANSITIONS
        assert events[-1].to_status == self.req.status

    @invariant()
    def timestamps_consistent(self):
        assert (self.req.resolved_at is not None) == (self.req.status in (Status.RESOLVED, Status.CLOSED))
        assert (self.req.closed_at is not None) == (self.req.status == Status.CLOSED)
        assert (self.req.merged_into_id is not None) == (self.req.status == Status.MERGED)


@pytest.mark.django_db
def test_lifecycle_properties():
    run_state_machine_as_test(
        CaseLifecycle,
        settings=settings(max_examples=60, stateful_step_count=12, deadline=None,
                          suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]),
    )


# --- Database guards --------------------------------------------------------------------


def _raw(sql, params):
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(sql, params)


@pytest.mark.django_db
@pytest.mark.parametrize("frm,to", [(a, b) for a in Status for b in Status if a != b])
def test_trigger_matches_transition_table(make_request, frm, to):
    """Force the row into `frm` with triggers switched off, then try `to` with raw SQL.
    The database must allow exactly the pairs in TRANSITIONS. merged_into is kept consistent
    so that only the trigger, not the CHECK constraint, decides."""
    req, other = make_request(), make_request()

    def merged_into(status):
        return other.pk if status == Status.MERGED else None

    with connection.cursor() as cur:
        cur.execute("SET LOCAL session_replication_role = replica")  # skips triggers
        cur.execute("UPDATE requests_app_servicerequest SET status=%s, merged_into_id=%s WHERE id=%s",
                    [frm.value, merged_into(frm), req.pk])
        cur.execute("SET LOCAL session_replication_role = DEFAULT")
    update = ("UPDATE requests_app_servicerequest SET status=%s, merged_into_id=%s WHERE id=%s",
              [to.value, merged_into(to), req.pk])
    if (frm, to) in TRANSITIONS:
        _raw(*update)
    else:
        with pytest.raises(IntegrityError, match="illegal status transition"):
            _raw(*update)


@pytest.mark.django_db
def test_orm_bypass_is_rejected(make_request):
    req = make_request()
    with pytest.raises(IntegrityError, match="illegal status transition"), transaction.atomic():
        ServiceRequest.objects.filter(pk=req.pk).update(status=Status.CLOSED)


@pytest.mark.django_db
def test_new_reports_must_start_pending(make_request):
    req = make_request()
    with pytest.raises(IntegrityError, match="must start as pending"):
        _raw(
            """INSERT INTO requests_app_servicerequest
               (citizen_id, category_id, ward_id, latitude, longitude, location_approximate, landmark, description, status,
                created_at, updated_at, due_at, escalation_level, source, external_ref)
               SELECT citizen_id, category_id, ward_id, latitude, longitude, false, '', 'x', 'resolved',
                      now(), now(), now(), 0, 'web', '' FROM requests_app_servicerequest WHERE id=%s""",
            [req.pk],
        )


@pytest.mark.django_db
@pytest.mark.parametrize("sql", ["UPDATE requests_app_caseevent SET note='edited' WHERE request_id=%s",
                                 "DELETE FROM requests_app_caseevent WHERE request_id=%s"])
def test_history_is_append_only(make_request, sql):
    req = make_request()
    with pytest.raises((InternalError, DatabaseError), match="append-only"):
        _raw(sql, [req.pk])
    assert req.events.count() == 1


# --- Named scenarios --------------------------------------------------------------------


@pytest.mark.django_db
def test_full_happy_path(make_request, citizen, water_officer):
    req = make_request()
    services.transition(req, Status.IN_PROGRESS, water_officer)
    services.transition(req, Status.RESOLVED, water_officer, note="Replaced the valve")
    services.transition(req, Status.CLOSED, citizen)
    assert [e.to_status for e in req.events.filter(kind="status")] == ["pending", "in_progress", "resolved", "closed"]
    assert [e.actor_role for e in req.events.filter(kind="status")] == ["owner", "officer", "officer", "owner"]


@pytest.mark.django_db
def test_reopen_clears_resolution(make_request, citizen, water_officer):
    req = make_request()
    services.transition(req, Status.IN_PROGRESS, water_officer)
    services.transition(req, Status.RESOLVED, water_officer, note="Fixed")
    services.transition(req, Status.IN_PROGRESS, citizen, note="Still leaking")
    req.refresh_from_db()
    assert req.status == Status.IN_PROGRESS and req.resolved_at is None


@pytest.mark.django_db
def test_officer_of_another_department_cannot_act(make_request, roads_officer):
    req = make_request("water_leak")
    with pytest.raises(statemachine.TransitionNotPermitted):
        services.transition(req, Status.IN_PROGRESS, roads_officer)


@pytest.mark.django_db
def test_resolving_needs_a_note(make_request, water_officer):
    req = make_request()
    services.transition(req, Status.IN_PROGRESS, water_officer)
    with pytest.raises(statemachine.NoteRequired):
        services.transition(req, Status.RESOLVED, water_officer, note="   ")


@pytest.mark.django_db
def test_merge_moves_people_to_surviving_case(make_request, citizen, other_citizen, make_user, water_officer):
    original = make_request(owner=citizen)
    duplicate = make_request(owner=other_citizen)
    follower = make_user()
    services.follow(duplicate, follower)
    services.transition(duplicate, Status.MERGED, water_officer, note="Same leak", merge_into=original)
    assert set(original.followers.values_list("user_id", flat=True)) == {other_citizen.pk, follower.pk}
    assert original.events.filter(kind="merge").count() == 1


@pytest.mark.django_db
def test_cannot_merge_into_different_category_or_closed(make_request, water_officer, citizen):
    leak = make_request("water_leak")
    sewer = make_request("sewer_blockage")
    with pytest.raises(statemachine.IllegalTransition, match="same problem type"):
        services.transition(leak, Status.MERGED, water_officer, note="x", merge_into=sewer)
    other = make_request("water_leak")
    services.transition(other, Status.IN_PROGRESS, water_officer)
    services.transition(other, Status.RESOLVED, water_officer, note="done")
    with pytest.raises(statemachine.IllegalTransition, match="still open"):
        services.transition(leak, Status.MERGED, water_officer, note="x", merge_into=other)
