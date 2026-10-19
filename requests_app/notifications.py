"""
SMS through Africa's Talking.

Messages are written to the Notification outbox inside the caller's transaction, then sent
once that transaction commits, so a rolled-back status change never sends an SMS and a
provider outage never blocks a status change. Messages carry the case reference and status
only, never the description or location, because an SMS can be read by anyone holding the phone.
"""

import logging

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.phone import is_sms_reachable

from .models import Notification, Status

log = logging.getLogger(__name__)

SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
LIVE_URL = "https://api.africastalking.com/version1/messaging"

STATUS_MESSAGES = {
    Status.IN_PROGRESS: "is now being worked on",
    Status.RESOLVED: "has been marked resolved. Please confirm it is fixed, or reopen it",
    Status.CLOSED: "is closed. Thank you for reporting",
    Status.MERGED: "was the same problem as another report and has been merged; you will get that report's updates",
}


def _queue(request_obj, phones, message):
    rows = [
        Notification(request=request_obj, phone=phone, message=message[:320])
        for phone in sorted(set(phones))
        if is_sms_reachable(phone)
    ]
    if not rows:
        return
    created = Notification.objects.bulk_create(rows)
    ids = [n.pk for n in created]
    transaction.on_commit(lambda: send_pending(ids=ids))


def _recipients(req, include_followers=True):
    phones = [req.citizen.phone]
    if include_followers:
        phones += list(req.followers.values_list("user__phone", flat=True))
    return phones


def queue_for_request(req, message, include_followers=True):
    _queue(req, _recipients(req, include_followers), message)


def queue_status_update(req, note=""):
    if req.status == Status.IN_PROGRESS and req.events.filter(to_status=Status.RESOLVED).exists():
        what = "has been reopened and is being worked on again"
    else:
        what = STATUS_MESSAGES.get(req.status)
    if not what:
        return
    message = f"Murang'a County: report {req.reference} ({req.category.name}) {what}. {settings.SITE_URL}/requests/{req.pk}/"
    queue_for_request(req, message)


def queue_escalation(req, level):
    phone = req.category.department.escalation_phone
    message = (
        f"Murang'a County ESCALATION L{level}: {req.reference} ({req.category.name}, {req.ward.name}) "
        f"is past its {req.category.target_label} target."
    )
    _queue(req, [phone], message)


def send_pending(ids=None):
    """Send queued messages (all of them, or just `ids`). Returns the number sent."""
    qs = Notification.objects.filter(state__in=[Notification.State.QUEUED, Notification.State.FAILED], attempts__lt=5)
    if ids is not None:
        qs = qs.filter(pk__in=ids)
    sent = 0
    for note in qs:
        state, response = _send_one(note.phone, note.message)
        note.attempts += 1
        note.state = state
        note.provider_response = response[:2000]
        if state == Notification.State.SENT:
            note.sent_at = timezone.now()
            sent += 1
        note.save(update_fields=["attempts", "state", "provider_response", "sent_at"])
    return sent


def _send_one(phone, message):
    if not settings.AT_API_KEY:
        log.info("SMS (not sent, AT_API_KEY unset) to %s: %s", phone, message)
        return Notification.State.SKIPPED, "AT_API_KEY not configured"
    url = SANDBOX_URL if settings.AT_USERNAME == "sandbox" else LIVE_URL
    data = {"username": settings.AT_USERNAME, "to": phone, "message": message}
    if settings.AT_SENDER_ID:
        data["from"] = settings.AT_SENDER_ID
    try:
        resp = requests.post(
            url, data=data, timeout=10,
            headers={"apiKey": settings.AT_API_KEY, "Accept": "application/json"},
        )
        body = resp.text
        recipients = resp.json().get("SMSMessageData", {}).get("Recipients", []) if resp.ok else []
    except (requests.RequestException, ValueError) as exc:
        log.warning("SMS to %s failed: %s", phone, exc)
        return Notification.State.FAILED, str(exc)
    # Africa's Talking status code 101 = "Sent" (accepted for delivery).
    if recipients and recipients[0].get("statusCode") in (100, 101, 102):
        return Notification.State.SENT, body
    log.warning("SMS to %s rejected: %s", phone, body)
    return Notification.State.FAILED, body
