from unittest import mock

import pytest

from requests_app import notifications, services
from requests_app.models import Notification, Status

AT_OK = {"SMSMessageData": {"Recipients": [{"statusCode": 101, "status": "Success", "number": "+254700000000"}]}}


@pytest.fixture
def at_sandbox(settings):
    settings.AT_API_KEY = "sandbox-test-key"
    settings.AT_USERNAME = "sandbox"
    with mock.patch("requests_app.notifications.requests.post") as post:
        post.return_value.ok = True
        post.return_value.text = "{}"
        post.return_value.json.return_value = AT_OK
        yield post


@pytest.mark.django_db
def test_status_change_texts_owner_and_followers(make_request, make_user, water_officer, at_sandbox,
                                                 django_capture_on_commit_callbacks):
    req = make_request()
    follower = make_user()
    services.follow(req, follower)
    at_sandbox.reset_mock()
    with django_capture_on_commit_callbacks(execute=True):
        services.transition(req, Status.IN_PROGRESS, water_officer)
    sent_to = sorted(call.kwargs["data"]["to"] for call in at_sandbox.call_args_list)
    assert sent_to == sorted([req.citizen.phone, follower.phone])
    call = at_sandbox.call_args_list[0]
    assert call.args[0] == notifications.SANDBOX_URL
    assert call.kwargs["headers"]["apiKey"] == "sandbox-test-key"
    assert req.reference in call.kwargs["data"]["message"]


@pytest.mark.django_db
def test_messages_carry_no_description_or_location(make_request, water_officer, at_sandbox,
                                                   django_capture_on_commit_callbacks):
    req = make_request()
    with django_capture_on_commit_callbacks(execute=True):
        services.transition(req, Status.IN_PROGRESS, water_officer)
    for n in Notification.objects.filter(request=req):
        assert req.description not in n.message and req.ward.name not in n.message
        assert len(n.message) <= 320


@pytest.mark.django_db
def test_nothing_is_sent_if_the_change_rolls_back(make_request, water_officer, at_sandbox,
                                                  django_capture_on_commit_callbacks):
    req = make_request()
    at_sandbox.reset_mock()
    with pytest.raises(RuntimeError), django_capture_on_commit_callbacks(execute=True):
        with mock.patch("requests_app.services.CaseEvent.objects.create", side_effect=RuntimeError("db down")):
            services.transition(req, Status.IN_PROGRESS, water_officer)
    at_sandbox.assert_not_called()
    req.refresh_from_db()
    assert req.status == Status.PENDING


@pytest.mark.django_db
def test_provider_failure_is_kept_for_retry(make_request, water_officer, at_sandbox,
                                            django_capture_on_commit_callbacks):
    import requests
    at_sandbox.side_effect = requests.ConnectionError("network down")
    req = make_request()
    with django_capture_on_commit_callbacks(execute=True):
        services.transition(req, Status.IN_PROGRESS, water_officer)
    failed = Notification.objects.filter(request=req, state=Notification.State.FAILED)
    assert failed.exists()
    at_sandbox.side_effect = None
    assert notifications.send_pending() >= failed.count()
    assert not Notification.objects.filter(request=req, state=Notification.State.FAILED).exists()


@pytest.mark.django_db
def test_without_api_key_messages_are_skipped_not_lost(make_request, water_officer, django_capture_on_commit_callbacks):
    req = make_request()
    with django_capture_on_commit_callbacks(execute=True):
        services.transition(req, Status.IN_PROGRESS, water_officer)
    update = Notification.objects.filter(request=req, message__contains="being worked on")
    assert update.exists() and set(update.values_list("state", flat=True)) == {"skipped"}


@pytest.mark.django_db
def test_escalation_runs_once_per_level(make_request, settings, at_sandbox, django_capture_on_commit_callbacks):
    from datetime import timedelta
    from django.utils import timezone
    req = make_request("pipe_burst")  # 25 clock hours
    req.category.department.escalation_phone = "+254711000000"
    req.category.department.save()
    later = timezone.now() + timedelta(hours=26)
    with django_capture_on_commit_callbacks(execute=True):
        assert services.escalate_overdue(now=later) == 1
        assert services.escalate_overdue(now=later) == 0
        assert services.escalate_overdue(now=later + timedelta(hours=25)) == 1
    req.refresh_from_db()
    assert req.escalation_level == 2
    assert req.events.filter(kind="escalation").count() == 2
    assert Notification.objects.filter(phone="+254711000000").count() == 2


@pytest.mark.django_db
def test_resolved_cases_close_themselves_after_grace_period(make_request, water_officer):
    from datetime import timedelta
    from django.utils import timezone
    req = make_request()
    services.transition(req, Status.IN_PROGRESS, water_officer)
    services.transition(req, Status.RESOLVED, water_officer, note="Fixed")
    assert services.auto_close_resolved(now=timezone.now() + timedelta(days=6)) == 0
    assert services.auto_close_resolved(now=timezone.now() + timedelta(days=8)) == 1
    req.refresh_from_db()
    assert req.status == Status.CLOSED and req.events.last().actor_role == "system"
