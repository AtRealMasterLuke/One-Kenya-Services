from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from open311.models import ApiKey

from . import analytics, services, statemachine
from .access import FULL, staff_queryset, staff_required, visible_request_or_404
from .forms import DetailsForm, LocateForm, NoteForm
from .geo import make_point, possible_duplicates, ward_for
from .models import Category, ServiceRequest, Status, Ward

DRAFT_KEY = "draft_report"


def home(request):
    if request.user.is_authenticated and request.user.is_county_staff:
        return redirect("staff_queue")
    categories = Category.objects.select_related("department")
    return render(request, "home.html", {"categories": categories})


# --- Citizens -------------------------------------------------------------------------


@login_required
def my_requests(request):
    reqs = (
        ServiceRequest.objects.filter(Q(citizen=request.user) | Q(followers__user=request.user))
        .select_related("category", "ward")
        .distinct()
        .order_by("-created_at")
    )
    return render(request, "requests/my_list.html", {"requests": reqs, "now": timezone.now()})


@login_required
def request_new(request):
    """Step 1: category and location, then a check for nearby open reports of the same thing."""
    form = LocateForm(request.POST or None, initial=request.session.get(DRAFT_KEY, {}).get("initial"))
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        category = data["category"]
        if data["latitude"] is not None and data["longitude"] is not None:
            point = make_point(data["latitude"], data["longitude"])
            ward = ward_for(point)
            if ward is None:
                form.add_error(None, "That spot is outside Murang'a County. Move the pin to where the problem is.")
                return render(request, "requests/new_locate.html", _locate_context(form))
            draft = {"latitude": data["latitude"], "longitude": data["longitude"]}
            duplicates = list(possible_duplicates(category, point, timezone.now())[:5])
        else:
            ward = data["ward"]
            draft = {"ward": ward.pk}
            duplicates = []
        draft.update(category=category.pk)
        request.session[DRAFT_KEY] = {"data": draft, "initial": {"category": category.pk}}
        if duplicates:
            return render(
                request, "requests/new_duplicates.html",
                {"duplicates": duplicates, "category": category, "ward": ward,
                 "radius": settings.DUPLICATE_RADIUS_METRES},
            )
        return redirect("request_new_details")
    return render(request, "requests/new_locate.html", _locate_context(form))


def _locate_context(form):
    return {"form": form, "categories": Category.objects.select_related("department")}


@login_required
def request_new_details(request):
    """Step 2: description, landmark, photo."""
    draft = request.session.get(DRAFT_KEY, {}).get("data")
    if not draft:
        return redirect("request_new")
    category = Category.objects.get(pk=draft["category"])
    ward = Ward.objects.get(pk=draft["ward"]) if "ward" in draft else None
    form = DetailsForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        point = make_point(draft["latitude"], draft["longitude"]) if "latitude" in draft else None
        try:
            req = services.create_request(
                citizen=request.user, category=category, point=point, ward=ward,
                description=form.cleaned_data["description"], landmark=form.cleaned_data["landmark"],
                photo=form.cleaned_data["photo"],
            )
        except services.OutsideCounty as exc:
            messages.error(request, str(exc))
            return redirect("request_new")
        del request.session[DRAFT_KEY]
        messages.success(request, f"Report {req.reference} sent. We'll text you when its status changes.")
        return redirect("request_detail", pk=req.pk)
    return render(request, "requests/new_details.html", {"form": form, "category": category, "ward": ward})


@login_required
@require_POST
def request_follow(request, pk):
    req = ServiceRequest.objects.filter(pk=pk, status__in=(Status.PENDING, Status.IN_PROGRESS)).first()
    if req is None:
        raise Http404
    services.follow(req, request.user)
    request.session.pop(DRAFT_KEY, None)
    messages.success(request, f"You're following {req.reference}. We'll text you when its status changes.")
    return redirect("my_requests")


@login_required
def request_detail(request, pk):
    req, level = visible_request_or_404(request.user, pk)
    context = {"req": req, "full": level == FULL, "now": timezone.now()}
    if level == FULL:
        context["events"] = req.events.select_related("actor").all()
        context["actions"] = [
            {"to": to, "label": statemachine.ACTION_LABELS.get((req.status, to)),
             "note_required": (req.status, to) in statemachine.NOTE_REQUIRED}
            for to in statemachine.allowed_targets(req, request.user) if to != Status.MERGED
        ]
        context["can_merge"] = Status.MERGED in statemachine.allowed_targets(req, request.user)
        if context["can_merge"] and not req.location_approximate:
            context["merge_candidates"] = possible_duplicates(req.category, req.location, req.created_at, exclude_pk=req.pk)[:10]
        context["note_form"] = NoteForm()
    else:
        context["events"] = req.events.filter(kind="status")
    return render(request, "requests/detail.html", context)


@login_required
def request_photo(request, pk):
    req, level = visible_request_or_404(request.user, pk)
    if level != FULL or not hasattr(req, "photo"):
        raise Http404
    response = HttpResponse(bytes(req.photo.data), content_type=req.photo.content_type)
    response["Cache-Control"] = "private, max-age=3600"
    return response


@login_required
@require_POST
def request_action(request, pk):
    req, level = visible_request_or_404(request.user, pk)
    if level != FULL:
        raise Http404
    to_status = request.POST.get("to_status")
    if to_status not in Status.values:
        messages.error(request, "Unknown action.")
        return redirect("request_detail", pk=pk)
    merge_into = None
    if to_status == Status.MERGED:
        merge_into = ServiceRequest.objects.filter(pk=request.POST.get("merge_into") or 0).first()
    form = NoteForm(request.POST)
    note = form.cleaned_data["note"] if form.is_valid() else ""
    try:
        services.transition(req, to_status, request.user, note=note, merge_into=merge_into)
    except statemachine.TransitionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{req.reference} is now {Status(to_status).label.lower()}.")
    return redirect("request_detail", pk=pk)


@login_required
def api_keys(request):
    new_key = None
    if request.method == "POST":
        if revoke := request.POST.get("revoke"):
            ApiKey.objects.filter(pk=revoke, user=request.user, revoked_at__isnull=True).update(revoked_at=timezone.now())
            messages.success(request, "Key revoked.")
        else:
            _, new_key = ApiKey.objects.issue(request.user, name=(request.POST.get("name") or "Open311 client")[:60])
    keys = request.user.api_keys.order_by("-created_at")
    return render(request, "requests/api_keys.html", {"keys": keys, "new_key": new_key})


# --- County staff ---------------------------------------------------------------------


QUEUE_STATUS_FILTERS = {
    "open": (Status.PENDING, Status.IN_PROGRESS),
    "pending": (Status.PENDING,),
    "in_progress": (Status.IN_PROGRESS,),
    "resolved": (Status.RESOLVED,),
    "closed": (Status.CLOSED, Status.MERGED),
}


QUEUE_STATUS_OPTIONS = [("open", "Open (pending + in progress)"), ("pending", "Pending"),
                        ("in_progress", "In progress"), ("resolved", "Resolved, awaiting citizen"),
                        ("closed", "Closed or merged")]


@staff_required
def staff_queue(request):
    qs = staff_queryset(request.user)
    status = request.GET.get("status", "open")
    qs = qs.filter(status__in=QUEUE_STATUS_FILTERS.get(status, QUEUE_STATUS_FILTERS["open"]))
    if ward := request.GET.get("ward"):
        qs = qs.filter(ward_id=ward)
    if category := request.GET.get("category"):
        qs = qs.filter(category__code=category)
    now = timezone.now()
    if request.GET.get("overdue"):
        qs = qs.filter(due_at__lt=now)
    if request.GET.get("live"):
        qs = qs.exclude(source=ServiceRequest.Source.REPLAY)
    # Most urgent first: earliest deadline at the top, so overdue cases lead.
    page = Paginator(qs.order_by("due_at", "id"), 50).get_page(request.GET.get("page"))
    categories = Category.objects.all()
    if request.user.department_id:
        categories = categories.filter(department_id=request.user.department_id)
    return render(request, "staff/queue.html", {
        "page": page, "now": now, "wards": Ward.objects.all(), "categories": categories,
        "filters": request.GET, "status": status, "status_options": QUEUE_STATUS_OPTIONS, "overdue_count": staff_queryset(request.user).filter(
            status__in=(Status.PENDING, Status.IN_PROGRESS), due_at__lt=now).count(),
    })


@staff_required
def staff_analytics(request):
    as_of = _parse_as_of(request.GET.get("as_of")) or timezone.now()
    source = request.GET.get("source") or None
    if source not in (None, *ServiceRequest.Source.values):
        source = None
    result = analytics.compute(as_of, source=source)
    if request.GET.get("format") == "json":
        return JsonResponse(result)
    names = {
        "category": dict(Category.objects.values_list("code", "name")),
        "ward": {code: f"{name} ({c})" for code, name, c in Ward.objects.values_list("code", "name", "constituency")},
    }
    by_category = [(names["category"].get(k, k), v) for k, v in result["by_category"].items()]
    by_ward = sorted(((names["ward"].get(k, k), v) for k, v in result["by_ward"].items()),
                     key=lambda item: -item[1]["open"])
    return render(request, "staff/analytics.html", {
        "result": result, "as_of": timezone.localtime(as_of), "source": source or "",
        "tables": [("By problem", by_category), ("By ward (most open cases first)", by_ward)],
        "sources": ServiceRequest.Source.choices,
    })


def _parse_as_of(value):
    if not value:
        return None
    try:
        return timezone.make_aware(datetime.fromisoformat(value))
    except ValueError:
        return None
