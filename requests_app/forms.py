from django import forms

from .models import Category, Ward
from .photos import process_upload


class CategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, category):
        return category.name


class LocateForm(forms.Form):
    """Step 1: what and where. Kept separate so we can show nearby reports of the same
    problem before the citizen spends time writing a description."""

    category = CategoryChoiceField(
        queryset=Category.objects.select_related("department"),
        widget=forms.RadioSelect,
        empty_label=None,
        label="What is the problem?",
    )
    latitude = forms.FloatField(required=False, min_value=-90, max_value=90, widget=forms.HiddenInput)
    longitude = forms.FloatField(required=False, min_value=-180, max_value=180, widget=forms.HiddenInput)
    ward = forms.ModelChoiceField(
        queryset=Ward.objects.all(),
        required=False,
        label="Or choose the ward",
        help_text="Use this if you can't use the map. Officers will rely on the landmark you give next.",
    )

    def clean(self):
        data = super().clean()
        has_point = data.get("latitude") is not None and data.get("longitude") is not None
        if not has_point and not data.get("ward"):
            raise forms.ValidationError(
                "Show us where the problem is: use your location, tap the map, or choose the ward."
            )
        return data


class DetailsForm(forms.Form):
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "maxlength": 2000}),
        min_length=10,
        max_length=2000,
        label="Describe the problem",
        help_text="What is wrong and since when. Don't include anyone's personal details.",
    )
    landmark = forms.CharField(
        required=False,
        max_length=200,
        label="Nearest landmark",
        help_text="For example: opposite Mukuyu market, next to St. Mary's church.",
    )
    photo = forms.ImageField(
        required=False,
        label="Photo (optional)",
        help_text="JPEG, PNG or WebP, up to 4 MB. Location data is removed from the photo before it is saved.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    def clean_photo(self):
        uploaded = self.cleaned_data.get("photo")
        if not uploaded:
            return None
        uploaded.seek(0)
        return process_upload(uploaded)


class NoteForm(forms.Form):
    note = forms.CharField(
        required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 2}), label="Note (kept in the history)"
    )
