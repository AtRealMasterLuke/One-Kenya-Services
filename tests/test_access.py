"""
"No citizen can read another citizen's requests", proven over HTTP against every URL that
exposes a case, for every kind of visitor. A stranger gets the same 404 as for a report that
doesn't exist, so IDs can't be probed for existence either.
"""

import pytest
from django.urls import reverse

from requests_app import services
from requests_app.models import Photo, Status

CASE_URLS = ["request_detail", "request_photo"]


@pytest.fixture
def case(make_request, citizen):
    req = make_request("water_leak", owner=citizen)
    Photo.objects.create(request=req, data=b"\xff\xd8fake", content_type="image/jpeg", width=1, height=1)
    return req


def login(client, user):
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", CASE_URLS)
def test_other_citizen_gets_404(client, case, other_citizen, url_name):
    login(client, other_citizen)
    assert client.get(reverse(url_name, args=[case.pk])).status_code == 404


@pytest.mark.django_db
def test_other_citizen_cannot_act_on_it(client, case, other_citizen):
    login(client, other_citizen)
    resp = client.post(reverse("request_action", args=[case.pk]), {"to_status": "closed"})
    assert resp.status_code == 404
    case.refresh_from_db()
    assert case.status == Status.PENDING


@pytest.mark.django_db
def test_nonexistent_and_forbidden_look_the_same(client, case, other_citizen):
    login(client, other_citizen)
    forbidden = client.get(reverse("request_detail", args=[case.pk]))
    missing = client.get(reverse("request_detail", args=[case.pk + 10_000]))
    assert forbidden.status_code == missing.status_code == 404


@pytest.mark.django_db
def test_other_citizens_report_never_in_my_list(client, case, other_citizen):
    login(client, other_citizen)
    body = client.get(reverse("my_requests")).content.decode()
    assert case.reference not in body


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", CASE_URLS)
def test_anonymous_is_sent_to_login(client, case, url_name):
    resp = client.get(reverse(url_name, args=[case.pk]))
    assert resp.status_code == 302 and reverse("login") in resp["Location"]


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", CASE_URLS)
def test_owner_sees_everything(client, case, citizen, url_name):
    login(client, citizen)
    assert client.get(reverse(url_name, args=[case.pk])).status_code == 200


@pytest.mark.django_db
def test_follower_sees_summary_without_description_or_photo(client, case, other_citizen):
    services.follow(case, other_citizen)
    login(client, other_citizen)
    body = client.get(reverse("request_detail", args=[case.pk])).content.decode()
    assert case.reference in body
    assert case.description not in body
    assert reverse("request_photo", args=[case.pk]) not in body
    assert client.get(reverse("request_photo", args=[case.pk])).status_code == 404


@pytest.mark.django_db
def test_officer_of_responsible_department_sees_it(client, case, water_officer):
    login(client, water_officer)
    body = client.get(reverse("request_detail", args=[case.pk])).content.decode()
    assert case.description in body and case.citizen.phone in body


@pytest.mark.django_db
def test_officer_of_another_department_gets_404(client, case, roads_officer):
    login(client, roads_officer)
    assert client.get(reverse("request_detail", args=[case.pk])).status_code == 404
    assert case.reference not in client.get(reverse("staff_queue")).content.decode()


@pytest.mark.django_db
def test_admin_sees_it(client, case, admin_user):
    login(client, admin_user)
    assert client.get(reverse("request_detail", args=[case.pk])).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["staff_queue", "staff_analytics"])
def test_citizens_cannot_open_staff_pages(client, citizen, url_name):
    login(client, citizen)
    assert client.get(reverse(url_name)).status_code == 403


@pytest.mark.django_db
def test_open311_public_view_is_redacted(client, case):
    """Open311 lists requests publicly, by design, but without anything personal."""
    item = client.get(f"/open311/v2/requests/{case.pk}.json").json()[0]
    text = str(item)
    assert case.description not in text
    assert case.citizen.phone not in text and case.citizen.full_name not in text
    assert "media_url" not in item
    assert round(item["lat"], 3) == item["lat"] and round(item["long"], 3) == item["long"]
