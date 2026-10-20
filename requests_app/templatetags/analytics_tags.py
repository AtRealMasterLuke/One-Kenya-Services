from django import template

from requests_app.models import Status

register = template.Library()

BAND_LABELS = {
    "under_2_days": "Under 2 days",
    "2_to_7_days": "2 to 7 days",
    "7_to_30_days": "7 to 30 days",
    "over_30_days": "Over 30 days",
}


@register.filter
def hours(value):
    """Hours as a readable duration: 5.5 -> '5.5 h', 50 -> '2.1 days'."""
    if value is None:
        return "–"
    if value < 48:
        return f"{value:.1f} h"
    return f"{value / 24:.1f} days"


@register.filter
def percent(value):
    return "–" if value is None else f"{value * 100:.0f}%"


@register.filter
def pct_bucket(value):
    return 0 if value is None else int(round(value * 20)) * 5


@register.filter
def band_label(key):
    return BAND_LABELS.get(key, key)


@register.filter
def status_label(value):
    """'in_progress' -> 'In progress', for history entries that store the raw status."""
    try:
        return Status(value).label
    except ValueError:
        return value
