from django.forms.renderers import TemplatesSetting


class FormRenderer(TemplatesSetting):
    """Every form field renders through templates/includes/field.html, so labels, help text
    and errors are wired up for screen readers the same way everywhere."""

    field_template_name = "includes/field.html"
