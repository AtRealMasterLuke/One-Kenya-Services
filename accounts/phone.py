import re

from django.core.exceptions import ValidationError

# Kenyan mobile numbers: 07xx / 01xx locally, +254 7xx / +254 1xx internationally.
_LOCAL = re.compile(r"^0([71]\d{8})$")
_INTL = re.compile(r"^\+?254([71]\d{8})$")
E164_KENYA = re.compile(r"^\+254[71]\d{8}$")


def normalise_phone(raw):
    """Return a Kenyan mobile number in E.164 form (+2547XXXXXXXX) or raise ValidationError."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    for pattern in (_LOCAL, _INTL):
        if match := pattern.match(digits):
            return "+254" + match.group(1)
    raise ValidationError("Enter a Kenyan mobile number, for example 0712 345 678.", code="invalid_phone")


def is_sms_reachable(phone):
    return bool(phone) and bool(E164_KENYA.match(phone))
