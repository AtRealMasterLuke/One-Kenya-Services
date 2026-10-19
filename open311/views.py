from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from requests_app import services
from requests_app.geo import make_point
from requests_app.models import Category, ServiceRequest, Status

from . import serializers as s
from .models import ApiKey

DEFAULT_WINDOW = timedelta(days=90)
MAX_RESULTS = 1000


@require_GET
def discovery(request):
    base = request.build_absolute_uri("/open311/v2/")
    return JsonResponse({
        "changeset": "2026-10-19T00:00:00+03:00",
        "contact": "Murang'a County service requests (demo)",
        "key_service": f"{settings.SITE_URL}/account/api-keys/",
        "endpoints": [{
            "specification": "http://wiki.open311.org/GeoReport_v2",
            "url": base,
            "changeset": "2026-10-19T00:00:00+03:00",
            "type": "production",
            "formats": ["application/json", "text/xml"],
        }],
    })


@require_GET
def service_list(request, fmt):
    categories = Category.objects.select_related("department")
    return s.respond(fmt, "services", [s.service(c) for c in categories])


@require_GET
def service_definition(request, code, fmt):
    # No service has extra attributes (metadata=false), so there is nothing to define.
    if Category.objects.filter(code=code).exists():
        return s.error(fmt, 404, f"Service {code} has no additional attributes (metadata is false).")
    return s.error(fmt, 404, f"No service with code {code}.")


@csrf_exempt  # authenticated by api_key, never by cookie
@require_http_methods(["GET", "POST"])
def request_list(request, fmt):
    if request.method == "POST":
        return _create(request, fmt)
    return _search(request, fmt)


@require_GET
def request_detail(request, pk, fmt):
    req = _base_queryset().filter(pk=pk).first()
    if req is None:
        return s.error(fmt, 404, f"No service request {pk}.")
    return s.respond(fmt, "service_requests", [s.service_request(req)])


def _base_queryset():
    return ServiceRequest.objects.select_related("category__department", "ward")


def _search(request, fmt):
    qs = _base_queryset()
    params = request.GET
    if ids := params.get("service_request_id"):
        wanted = [i for i in ids.split(",") if i.strip().isdigit()]
        qs = qs.filter(pk__in=wanted)
    else:
        end = _parse_date(params.get("end_date"))
        start = _parse_date(params.get("start_date"))
        if start is False or end is False:
            return s.error(fmt, 400, "start_date and end_date must be W3C datetimes, e.g. 2026-10-01T00:00:00+03:00.")
        end = end or timezone.now()
        start = start or end - DEFAULT_WINDOW
        qs = qs.filter(created_at__gte=start, created_at__lte=end)
        if codes := params.get("service_code"):
            qs = qs.filter(category__code__in=codes.split(","))
        if status := params.get("status"):
            wanted = set(status.split(","))
            if not wanted <= {"open", "closed"}:
                return s.error(fmt, 400, "status must be open, closed, or both.")
            if wanted == {"open"}:
                qs = qs.filter(status__in=(Status.PENDING, Status.IN_PROGRESS))
            elif wanted == {"closed"}:
                qs = qs.exclude(status__in=(Status.PENDING, Status.IN_PROGRESS))
    items = [s.service_request(r) for r in qs.order_by("-created_at")[:MAX_RESULTS]]
    return s.respond(fmt, "service_requests", items)


def _parse_date(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return False
    return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)


def _create(request, fmt):
    data = request.POST
    # The spec puts api_key in the POST body, but Code for America's client libraries send it in
    # the query string, so accept both. (Query strings reach access logs; see docs/threat-model.md.)
    key = ApiKey.objects.authenticate(data.get("api_key") or request.GET.get("api_key"))
    if key is None:
        return s.error(fmt, 403, "A valid api_key is required. Citizens can create one on their account page.")
    category = Category.objects.filter(code=data.get("service_code", "")).first()
    if category is None:
        return s.error(fmt, 400, "Unknown or missing service_code.")
    try:
        point = make_point(data["lat"], data["long"])
    except (KeyError, ValueError):
        return s.error(fmt, 400, "lat and long are required (decimal degrees). Murang'a County is about lat -0.8, long 37.0.")
    description = (data.get("description") or "").strip()
    if len(description) < 10:
        return s.error(fmt, 400, "description is required (at least 10 characters).")
    try:
        req = services.create_request(
            citizen=key.user, category=category, point=point, description=description[:2000],
            landmark=(data.get("address_string") or "")[:200], source=ServiceRequest.Source.OPEN311,
        )
    except services.OutsideCounty as exc:
        return s.error(fmt, 400, str(exc))
    except ValidationError as exc:
        return s.error(fmt, 400, "; ".join(exc.messages))
    notice = f"Reference {req.reference}. Target: {category.target_label}."
    return s.respond(
        fmt, "service_requests",
        [{"service_request_id": str(req.pk), "service_notice": notice, "account_id": None}],
        status=201,
    )
