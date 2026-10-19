"""Open311 GeoReport v2 behaviour (http://wiki.open311.org/GeoReport_v2/)."""

import xml.etree.ElementTree as ET

import pytest

from open311.models import ApiKey
from requests_app.models import ServiceRequest


@pytest.fixture
def api_key(citizen):
    return ApiKey.objects.issue(citizen)[1]


def post(client, **data):
    return client.post("/open311/v2/requests.json", data)


@pytest.mark.django_db
def test_service_list(client):
    services = client.get("/open311/v2/services.json").json()
    assert {s["service_code"] for s in services} >= {"water_leak", "streetlight", "garbage_missed"}
    assert all(s["metadata"] is False and s["type"] == "realtime" for s in services)


@pytest.mark.django_db
def test_service_list_xml(client):
    root = ET.fromstring(client.get("/open311/v2/services.xml").content)
    assert root.tag == "services" and root.find("service/service_code") is not None


@pytest.mark.django_db
def test_post_creates_request_owned_by_key_holder(client, api_key, citizen, point_in):
    resp = post(client, api_key=api_key, service_code="pipe_burst", lat=point_in.y, long=point_in.x,
                description="Water gushing across the road", address_string="Near the stage")
    assert resp.status_code == 201
    body = resp.json()[0]
    req = ServiceRequest.objects.get(pk=body["service_request_id"])
    assert req.citizen == citizen and req.source == "open311" and req.landmark == "Near the stage"
    assert req.reference in body["service_notice"]


@pytest.mark.django_db
def test_post_without_csrf_token_still_works(api_key, point_in):
    """External clients have no CSRF cookie; Open311 POST is authenticated by api_key instead."""
    from django.test import Client
    resp = Client(enforce_csrf_checks=True).post("/open311/v2/requests.json", {
        "api_key": api_key, "service_code": "pipe_burst", "lat": point_in.y, "long": point_in.x,
        "description": "Water gushing across the road"})
    assert resp.status_code == 201


@pytest.mark.django_db
@pytest.mark.parametrize("key", ["", "wrong-key"])
def test_post_needs_valid_key(client, key, point_in):
    resp = post(client, api_key=key, service_code="pipe_burst", lat=point_in.y, long=point_in.x, description="x" * 20)
    assert resp.status_code == 403
    assert resp.json()[0]["code"] == 403


@pytest.mark.django_db
def test_revoked_key_is_refused(client, citizen, point_in):
    key, plaintext = ApiKey.objects.issue(citizen)
    key.revoked_at = key.created_at
    key.save()
    resp = post(client, api_key=plaintext, service_code="pipe_burst", lat=point_in.y, long=point_in.x, description="x" * 20)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_keys_are_stored_hashed(citizen):
    key, plaintext = ApiKey.objects.issue(citizen)
    assert plaintext not in key.digest and len(key.digest) == 64


@pytest.mark.django_db
@pytest.mark.parametrize("data,error", [
    ({"service_code": "nope", "lat": -0.72, "long": 37.15}, "service_code"),
    ({"service_code": "pipe_burst"}, "lat and long"),
    ({"service_code": "pipe_burst", "lat": -1.2864, "long": 36.8172}, "outside Murang'a"),
    ({"service_code": "pipe_burst", "lat": -0.72, "long": 37.15, "description": "short"}, "description"),
])
def test_post_validation(client, api_key, data, error):
    data = {"description": "A long enough description", **data, "api_key": api_key}
    resp = post(client, **data)
    assert resp.status_code == 400 and error in resp.json()[0]["description"]


@pytest.mark.django_db
def test_get_requests_filters(client, make_request, water_officer):
    from requests_app import services
    leak = make_request("water_leak")
    light = make_request("streetlight")
    services.transition(leak, "in_progress", water_officer)
    services.transition(leak, "resolved", water_officer, note="done")

    def ids(query):
        return {r["service_request_id"] for r in client.get(f"/open311/v2/requests.json?{query}").json()}

    assert ids("status=open") == {str(light.pk)}
    assert ids("status=closed") == {str(leak.pk)}
    assert ids("service_code=water_leak") == {str(leak.pk)}
    assert ids(f"service_request_id={leak.pk},{light.pk}") == {str(leak.pk), str(light.pk)}
    assert client.get("/open311/v2/requests.json?start_date=yesterday").status_code == 400


@pytest.mark.django_db
def test_get_single_request_xml(client, make_request):
    req = make_request()
    root = ET.fromstring(client.get(f"/open311/v2/requests/{req.pk}.xml").content)
    assert root.tag == "service_requests"
    assert root.find("request/service_request_id").text == str(req.pk)
    assert root.find("request/status").text == "open"


@pytest.mark.django_db
def test_unknown_request_404(client):
    resp = client.get("/open311/v2/requests/999999.json")
    assert resp.status_code == 404 and resp.json()[0]["code"] == 404


@pytest.mark.django_db
def test_api_key_in_query_string_is_accepted(client, api_key, point_in):
    """Code for America's open311 client sends api_key in the URL, not the body."""
    resp = client.post(f"/open311/v2/requests.json?api_key={api_key}", {
        "service_code": "pipe_burst", "lat": point_in.y, "long": point_in.x, "description": "Water gushing across the road"})
    assert resp.status_code == 201
