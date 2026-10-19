"""
The case lifecycle.

    pending ──start──▶ in_progress ──resolve──▶ resolved ──confirm/auto-close──▶ closed
       │                  ▲   │                    │
       │                  └───┼────── reopen ──────┘
       └──merge──▶ merged ◀───┘

TRANSITIONS is the single source of truth. services.transition() enforces it for every
change made through the application, and migration 0002 builds a database trigger from it
so that a status change made any other way is rejected too.
"""

from .models import Status

OWNER = "owner"  # the citizen who made the report
OFFICER = "officer"  # county officer in the category's department
ADMIN = "admin"
SYSTEM = "system"  # scheduled jobs and dataset replay

# (from, to) -> roles allowed to make that move
TRANSITIONS = {
    (Status.PENDING, Status.IN_PROGRESS): {OFFICER, ADMIN, SYSTEM},
    (Status.PENDING, Status.MERGED): {OFFICER, ADMIN},
    (Status.IN_PROGRESS, Status.RESOLVED): {OFFICER, ADMIN, SYSTEM},
    (Status.IN_PROGRESS, Status.MERGED): {OFFICER, ADMIN},
    (Status.RESOLVED, Status.CLOSED): {OWNER, SYSTEM},
    (Status.RESOLVED, Status.IN_PROGRESS): {OWNER, ADMIN},
}

# A reason is required whenever the move needs explaining to someone else later.
NOTE_REQUIRED = {
    (Status.IN_PROGRESS, Status.RESOLVED),
    (Status.RESOLVED, Status.IN_PROGRESS),
    (Status.PENDING, Status.MERGED),
    (Status.IN_PROGRESS, Status.MERGED),
}

TERMINAL = {Status.CLOSED, Status.MERGED}

# Button labels, from the point of view of whoever is allowed to press them.
ACTION_LABELS = {
    (Status.PENDING, Status.IN_PROGRESS): "Start work",
    (Status.IN_PROGRESS, Status.RESOLVED): "Mark resolved",
    (Status.RESOLVED, Status.CLOSED): "Yes, it's fixed",
    (Status.RESOLVED, Status.IN_PROGRESS): "No, reopen it",
}


class TransitionError(Exception):
    """Base class; the message is safe to show to the user."""


class IllegalTransition(TransitionError):
    pass


class TransitionNotPermitted(TransitionError):
    pass


class NoteRequired(TransitionError):
    pass


def role_of(actor, service_request):
    """The role an actor plays for one particular case."""
    if actor is None:
        return SYSTEM
    if actor.role == ADMIN:
        return ADMIN
    if actor.role == OFFICER and actor.department_id == service_request.category.department_id:
        return OFFICER
    if actor.pk == service_request.citizen_id:
        return OWNER
    return None


def allowed_targets(service_request, actor):
    role = role_of(actor, service_request)
    return [to for (frm, to), roles in TRANSITIONS.items() if frm == service_request.status and role in roles]


def check(from_status, to_status, role, note):
    if (from_status, to_status) not in TRANSITIONS:
        raise IllegalTransition(f"A report cannot go from {Status(from_status).label} to {Status(to_status).label}.")
    if role not in TRANSITIONS[(from_status, to_status)]:
        raise TransitionNotPermitted("You are not allowed to make this change to this report.")
    if (from_status, to_status) in NOTE_REQUIRED and not (note or "").strip():
        raise NoteRequired("Please say why. The note is kept in the report's history.")


def trigger_sql():
    """SQL for the database-level guard. Generated from TRANSITIONS so the two cannot drift;
    tests/test_state_machine.py checks the live trigger against TRANSITIONS as well."""
    pairs = " OR ".join(
        f"(OLD.status = '{frm.value}' AND NEW.status = '{to.value}')" for frm, to in sorted(TRANSITIONS)
    )
    return f"""
CREATE OR REPLACE FUNCTION requests_app_check_status_transition() RETURNS trigger AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status AND NOT ({pairs}) THEN
        RAISE EXCEPTION 'illegal status transition % -> %', OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS servicerequest_status_transition ON requests_app_servicerequest;
CREATE TRIGGER servicerequest_status_transition
    BEFORE UPDATE OF status ON requests_app_servicerequest
    FOR EACH ROW EXECUTE FUNCTION requests_app_check_status_transition();

CREATE OR REPLACE FUNCTION requests_app_new_request_is_pending() RETURNS trigger AS $$
BEGIN
    IF NEW.status <> 'pending' THEN
        RAISE EXCEPTION 'new reports must start as pending, got %', NEW.status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS servicerequest_starts_pending ON requests_app_servicerequest;
CREATE TRIGGER servicerequest_starts_pending
    BEFORE INSERT ON requests_app_servicerequest
    FOR EACH ROW EXECUTE FUNCTION requests_app_new_request_is_pending();
"""


APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION requests_app_case_event_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'case history is append-only (% rejected)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS caseevent_append_only ON requests_app_caseevent;
CREATE TRIGGER caseevent_append_only
    BEFORE UPDATE OR DELETE ON requests_app_caseevent
    FOR EACH ROW EXECUTE FUNCTION requests_app_case_event_append_only();
"""
