"""End-to-end flows over HTTP, as a citizen and an officer would use the site."""

import pytest
from django.urls import reverse

from accounts.models import User
from requests_app.models import ServiceRequest, Status
from tests.conftest import PASSWORD


def login(client, user):
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")


@pytest.mark.django_db
def test_register_normalises_phone_and_signs_in(client):
    resp = client.post(reverse("register"), {
        "full_name": "Njeri Wambui", "phone": "0712 345 678",
        "password1": "a-long-passphrase-9", "password2": "a-long-passphrase-9"})
    assert resp.status_code == 302
    assert User.objects.get(full_name="Njeri Wambui").phone == "+254712345678"
    assert client.get(reverse("my_requests")).status_code == 200


@pytest.mark.django_db
def test_register_rejects_non_kenyan_numbers(client):
    resp = client.post(reverse("register"), {
        "full_name": "X", "phone": "+44 7700 900000", "password1": "a-long-passphrase-9", "password2": "a-long-passphrase-9"})
    assert resp.status_code == 200 and b"Kenyan mobile number" in resp.content


@pytest.mark.django_db
def test_login_accepts_local_format(client, citizen):
    local = "0" + citizen.phone[4:]
    resp = client.post(reverse("login"), {"username": local, "password": PASSWORD})
    assert resp.status_code == 302


@pytest.mark.django_db
def test_lockout_after_five_failures(client, citizen):
    local = "0" + citizen.phone[4:]
    for attempt in range(5):
        client.post(reverse("login"), {"username": local if attempt % 2 else citizen.phone, "password": "wrong"})
    # Mixed number formats share one counter, and now even the right password is refused.
    resp = client.post(reverse("login"), {"username": citizen.phone, "password": PASSWORD})
    assert resp.status_code == 429


@pytest.mark.django_db
def test_report_flow_with_duplicate_check(client, citizen, other_citizen, make_request, point_in):
    existing = make_request("streetlight", owner=other_citizen)
    login(client, citizen)
    category = existing.category.pk
    resp = client.post(reverse("request_new"), {"category": category, "latitude": point_in.y, "longitude": point_in.x})
    assert resp.status_code == 200 and existing.reference.encode() in resp.content  # "Is it one of these?"
    assert existing.description.encode() not in resp.content  # someone else's description stays private

    # Citizen says it's a different problem and continues.
    resp = client.post(reverse("request_new_details"), {"description": "A different light, on the other pole."})
    new = ServiceRequest.objects.exclude(pk=existing.pk).get(citizen=citizen)
    assert resp.status_code == 302 and resp["Location"] == reverse("request_detail", args=[new.pk])
    assert new.suspected_duplicate == existing


@pytest.mark.django_db
def test_follow_instead_of_reporting(client, citizen, make_request, other_citizen):
    existing = make_request("streetlight", owner=other_citizen)
    login(client, citizen)
    client.post(reverse("request_follow", args=[existing.pk]))
    assert existing.followers.filter(user=citizen).exists()
    assert existing.reference in client.get(reverse("my_requests")).content.decode()


@pytest.mark.django_db
def test_ward_fallback_without_map(client, citizen, township):
    login(client, citizen)
    resp = client.post(reverse("request_new"), {"category": 1, "ward": township.pk})
    assert resp.status_code == 302
    client.post(reverse("request_new_details"), {"description": "Behind the market, no GPS on my phone."})
    req = ServiceRequest.objects.get(citizen=citizen)
    assert req.ward == township and req.location_approximate


@pytest.mark.django_db
def test_point_outside_county_is_explained(client, citizen):
    login(client, citizen)
    resp = client.post(reverse("request_new"), {"category": 1, "latitude": -1.2864, "longitude": 36.8172})
    assert resp.status_code == 200 and b"outside Murang" in resp.content


@pytest.mark.django_db
def test_officer_works_a_case_and_citizen_confirms(client, citizen, make_request, water_officer):
    req = make_request("water_leak")
    login(client, water_officer)
    client.post(reverse("request_action", args=[req.pk]), {"to_status": "in_progress"})
    resp = client.post(reverse("request_action", args=[req.pk]), {"to_status": "resolved", "note": ""}, follow=True)
    assert b"Please say why" in resp.content  # note required, shown to the officer
    client.post(reverse("request_action", args=[req.pk]), {"to_status": "resolved", "note": "Valve replaced"})
    login(client, citizen)
    client.post(reverse("request_action", args=[req.pk]), {"to_status": "closed"})
    req.refresh_from_db()
    assert req.status == Status.CLOSED


@pytest.mark.django_db
def test_queue_shows_overdue_first(client, water_officer, make_request):
    from datetime import timedelta
    from django.utils import timezone
    old = make_request("pipe_burst", created_at=timezone.now() - timedelta(days=3))
    new = make_request("pipe_burst")
    login(client, water_officer)
    body = client.get(reverse("staff_queue")).content.decode()
    assert body.index(old.reference) < body.index(new.reference)
    assert "is-overdue" in body


@pytest.mark.django_db
def test_security_headers(client):
    resp = client.get(reverse("home"))
    assert "default-src 'self'" in resp["Content-Security-Policy"]
    assert resp["X-Frame-Options"] == "DENY"
    assert resp["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
def test_reflected_form_values_are_escaped(client):
    """ZAP rule 10031 flags input echoed into attributes on the registration form. Prove the echo is
    escaped: the payload comes back as text inside value="…", never as markup."""
    payload = '"><script>alert(1)</script>'
    resp = client.post(reverse("register"), {
        "full_name": payload, "phone": "not-a-phone", "password1": "x", "password2": "y"})
    body = resp.content.decode()
    assert payload not in body
    assert "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in body


@pytest.mark.django_db
def test_cron_endpoint_needs_the_secret(client, settings):
    settings.CRON_SECRET = "s3cret"
    assert client.get("/cron/maintenance").status_code == 401
    assert client.get("/cron/maintenance", HTTP_AUTHORIZATION="Bearer wrong").status_code == 401
    resp = client.get("/cron/maintenance", HTTP_AUTHORIZATION="Bearer s3cret")
    assert resp.status_code == 200 and set(resp.json()) == {"escalated", "auto_closed", "sms_sent"}
