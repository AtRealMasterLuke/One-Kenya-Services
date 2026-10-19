from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm

from .models import User
from .phone import normalise_phone


class RegistrationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ["full_name", "phone"]
        labels = {"full_name": "Full name", "phone": "Mobile number"}
        help_texts = {"phone": "We send status updates to this number by SMS."}
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
        }

    def clean_phone(self):
        phone = normalise_phone(self.cleaned_data["phone"])
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("An account with this number already exists. Sign in instead.")
        return phone


class PhoneLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Mobile number", widget=forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "autofocus": True})
    )

    def clean_username(self):
        # Accept 07.. or +2547..; anything unparseable falls through and fails authentication.
        return username_for_lockout_raw(self.cleaned_data["username"])


def username_for_lockout_raw(raw):
    try:
        return normalise_phone(raw)
    except forms.ValidationError:
        return raw


def username_for_lockout(request, credentials):
    """django-axes hook: count failures per normalised number so 07.. and +2547.. share a counter."""
    raw = (credentials or {}).get("username") or request.POST.get("username", "")
    return username_for_lockout_raw(raw)
