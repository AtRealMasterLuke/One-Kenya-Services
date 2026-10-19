"""Open311 GeoReport v2 response shapes, in JSON or XML (http://wiki.open311.org/GeoReport_v2/)."""

import json
from xml.etree.ElementTree import Element, SubElement, tostring

from django.http import HttpResponse
from django.utils import timezone

from requests_app.models import OPEN_STATUSES, Status

# Reports are public in Open311 for transparency, but only coarsely: no description, photo or
# reporter, and coordinates rounded to 3 decimal places (about 110 m). See docs/decisions.md.
PUBLIC_COORDINATE_PLACES = 3

STATUS_NOTES = {
    Status.PENDING: "Received; waiting to be assigned.",
    Status.IN_PROGRESS: "Being worked on.",
    Status.RESOLVED: "Marked resolved; waiting for the reporter to confirm.",
    Status.CLOSED: "Closed.",
}


def _iso(dt):
    return timezone.localtime(dt).isoformat(timespec="seconds") if dt else None


def service(category):
    return {
        "service_code": category.code,
        "service_name": category.name,
        "description": f"{category.description} Target: {category.target_label}.",
        "metadata": False,
        "type": "realtime",
        "keywords": category.department.code,
        "group": category.department.name,
    }


def service_request(req):
    if req.status == Status.MERGED:
        notes = f"Duplicate of {req.merged_into_id}."
    else:
        notes = STATUS_NOTES[req.status]
    return {
        "service_request_id": str(req.pk),
        "status": "open" if req.status in OPEN_STATUSES else "closed",
        "status_notes": notes,
        "service_name": req.category.name,
        "service_code": req.category.code,
        "agency_responsible": req.category.department.name,
        "service_notice": "",
        "requested_datetime": _iso(req.created_at),
        "updated_datetime": _iso(req.updated_at),
        "expected_datetime": _iso(req.due_at),
        "address": f"{req.ward.name} ward, {req.ward.constituency}",
        "address_id": req.ward.code,
        "zipcode": None,
        "lat": round(req.location.y, PUBLIC_COORDINATE_PLACES),
        "long": round(req.location.x, PUBLIC_COORDINATE_PLACES),
    }


def _to_xml(root_name, item_name, items):
    root = Element(root_name)
    for item in items:
        node = SubElement(root, item_name)
        for key, value in item.items():
            SubElement(node, key).text = "" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
    return b'<?xml version="1.0" encoding="utf-8"?>' + tostring(root, encoding="utf-8")


ROOTS = {"services": ("services", "service"), "service_requests": ("service_requests", "request"), "errors": ("errors", "error")}


def respond(fmt, kind, items, status=200):
    if fmt == "xml":
        root, item = ROOTS[kind]
        return HttpResponse(_to_xml(root, item, items), content_type="text/xml; charset=utf-8", status=status)
    return HttpResponse(json.dumps(items), content_type="application/json", status=status)


def error(fmt, code, description):
    return respond(fmt, "errors", [{"code": code, "description": description}], status=code)
