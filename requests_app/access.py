"""
Who may see what. Every view that loads a case goes through visible_request_or_404, so the
rule "a citizen can only read their own reports" lives in one place.

  owner                       full report, photo, history, actions
  officer (same department)   full report, photo, history, actions
  admin                       full report, photo, history, actions
  follower                    summary only: category, ward, status, dates (no description/photo)
  anyone else                 404, the same response as for a report that doesn't exist
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404

from accounts.models import Role

from .models import ServiceRequest
from .statemachine import ADMIN, OFFICER, OWNER, role_of

FULL = "full"
SUMMARY = "summary"


def access_level(user, req):
    if role_of(user, req) in {OWNER, OFFICER, ADMIN}:
        return FULL
    if req.followers.filter(user=user).exists():
        return SUMMARY
    return None


def visible_request_or_404(user, pk):
    req = (
        ServiceRequest.objects.select_related("category__department", "ward", "citizen", "merged_into")
        .filter(pk=pk)
        .first()
    )
    level = access_level(user, req) if req else None
    if level is None:
        raise Http404("No such report")
    return req, level


def staff_queryset(user):
    """Cases a member of staff works on: their department's, or everything for an admin."""
    qs = ServiceRequest.objects.select_related("category__department", "ward")
    if user.role == Role.ADMIN:
        return qs
    return qs.filter(category__department_id=user.department_id)


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_county_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != Role.ADMIN:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
