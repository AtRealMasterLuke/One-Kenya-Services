"""
Every change to a case goes through this module, so the rules live in one place:
status changes are checked against the state machine, written to the append-only history
in the same transaction, and SMS updates are queued for after the commit.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import notifications, statemachine
from .deadlines import due_at
from .geo import possible_duplicates, ward_for
from .models import CaseEvent, Follower, ServiceRequest, Status


class OutsideCounty(Exception):
    pass


@transaction.atomic
def create_request(*, citizen, category, point=None, ward=None, description, landmark="", photo=None,
                   source=ServiceRequest.Source.WEB, created_at=None, external_ref=""):
    """Pass `point` for a pinned location, or only `ward` when the reporter could not use the map."""
    created_at = created_at or timezone.now()
    approximate = point is None
    if approximate:
        point = ward.shape.representative_point()
    else:
        ward = ward_for(point)
        if ward is None:
            raise OutsideCounty("That location is outside Murang'a County. Move the pin to where the problem is.")
    # Approximate locations all sit on the ward centre, so distance tells us nothing about duplicates.
    nearby = [] if approximate else possible_duplicates(category, point, created_at)
    duplicate = nearby[0] if nearby else None
    req = ServiceRequest.objects.create(
        citizen=citizen,
        category=category,
        ward=ward,
        latitude=point.y,
        longitude=point.x,
        location_approximate=approximate,
        landmark=landmark,
        description=description,
        created_at=created_at,
        due_at=due_at(created_at, category),
        suspected_duplicate=duplicate,
        source=source,
        external_ref=external_ref,
    )
    CaseEvent.objects.create(
        request=req, kind=CaseEvent.Kind.STATUS, from_status="", to_status=Status.PENDING,
        actor=citizen, actor_role=statemachine.OWNER, created_at=created_at,
    )
    if photo is not None:
        photo.request = req
        photo.save()
    if source != ServiceRequest.Source.REPLAY:
        notifications.queue_for_request(
            req, f"Murang'a County: we received your report {req.reference} ({category.name}). "
                 f"Target: {category.target_label}.",
            include_followers=False,
        )
    return req


@transaction.atomic
def transition(service_request, to_status, actor, note="", at=None, merge_into=None):
    """Move a case to `to_status`. Raises a statemachine.TransitionError subclass if the move
    is not allowed; nothing is written in that case."""
    at = at or timezone.now()
    req = ServiceRequest.objects.select_for_update().select_related("category").get(pk=service_request.pk)
    from_status = req.status
    role = statemachine.role_of(actor, req)
    statemachine.check(from_status, to_status, role, note)

    if to_status == Status.MERGED:
        target = _validate_merge_target(req, merge_into)
        req.merged_into = target

    req.status = to_status
    if to_status == Status.RESOLVED:
        req.resolved_at = at
    elif to_status == Status.IN_PROGRESS and from_status == Status.RESOLVED:
        req.resolved_at = None  # reopened: the earlier "resolution" did not hold
    if to_status == Status.CLOSED:
        req.closed_at = at
    req.save()

    CaseEvent.objects.create(
        request=req, kind=CaseEvent.Kind.STATUS, from_status=from_status, to_status=to_status,
        actor=actor, actor_role=role, note=note.strip(), created_at=at,
    )

    if to_status == Status.MERGED:
        _absorb_into(req, req.merged_into, actor, role, at)

    if req.source != ServiceRequest.Source.REPLAY:
        notifications.queue_status_update(req, note)
    service_request.refresh_from_db()
    return req


def _validate_merge_target(req, target):
    if target is None:
        raise statemachine.IllegalTransition("Choose the report this one duplicates.")
    target = ServiceRequest.objects.select_for_update().get(pk=target.pk)
    if target.pk == req.pk:
        raise statemachine.IllegalTransition("A report cannot be merged into itself.")
    if target.category_id != req.category_id:
        raise statemachine.IllegalTransition("Only reports of the same problem type can be merged.")
    if not target.is_open:
        raise statemachine.IllegalTransition("You can only merge into a report that is still open.")
    return target


def _absorb_into(duplicate, target, actor, role, at):
    """The duplicate's reporter and followers now follow the surviving case."""
    people = {duplicate.citizen_id} | set(duplicate.followers.values_list("user_id", flat=True))
    people.discard(target.citizen_id)
    for user_id in people:
        Follower.objects.get_or_create(request=target, user_id=user_id, defaults={"created_at": at})
    CaseEvent.objects.create(
        request=target, kind=CaseEvent.Kind.MERGE, actor=actor, actor_role=role, created_at=at,
        note=f"{duplicate.reference} was merged into this report.",
    )


@transaction.atomic
def follow(service_request, user):
    if service_request.citizen_id == user.pk:
        return False
    _, created = Follower.objects.get_or_create(request=service_request, user=user)
    if created:
        CaseEvent.objects.create(
            request=service_request, kind=CaseEvent.Kind.FOLLOW, actor=user, actor_role="follower",
        )
    return created


def escalate_overdue(now=None):
    """Level 1 when a case passes its deadline, level 2 when it is late by a whole second
    target period. Each level is recorded once and sends one SMS to the department."""
    now = now or timezone.now()
    escalated = 0
    candidates = ServiceRequest.objects.filter(status__in=(Status.PENDING, Status.IN_PROGRESS), due_at__lt=now)
    for req in candidates.select_related("category__department").exclude(source=ServiceRequest.Source.REPLAY):
        late_by = now - req.due_at
        level = 2 if late_by >= timedelta(hours=req.category.sla_hours) else 1
        if level <= req.escalation_level:
            continue
        with transaction.atomic():
            ServiceRequest.objects.filter(pk=req.pk).update(escalation_level=level)
            CaseEvent.objects.create(
                request=req, kind=CaseEvent.Kind.ESCALATION, actor=None, actor_role=statemachine.SYSTEM,
                created_at=now, note=f"Escalated to level {level}: past the {req.category.target_label} target.",
            )
            notifications.queue_escalation(req, level)
        escalated += 1
    return escalated


def auto_close_resolved(now=None):
    """Close cases whose resolution the citizen has not disputed within the grace period."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=settings.AUTO_CLOSE_RESOLVED_AFTER_DAYS)
    closed = 0
    for req in ServiceRequest.objects.filter(status=Status.RESOLVED, resolved_at__lt=cutoff):
        transition(
            req, Status.CLOSED, actor=None, at=now,
            note=f"Closed automatically: no response {settings.AUTO_CLOSE_RESOLVED_AFTER_DAYS} days after resolution.",
        )
        closed += 1
    return closed
