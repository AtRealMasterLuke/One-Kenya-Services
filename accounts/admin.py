from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["full_name"]
    list_display = ["full_name", "phone", "role", "department", "is_active"]
    list_filter = ["role", "department", "is_active"]
    search_fields = ["full_name", "phone"]
    fieldsets = [
        (None, {"fields": ["phone", "full_name", "password"]}),
        ("Role", {"fields": ["role", "department"]}),
        ("Access", {"fields": ["is_active", "is_staff", "is_superuser"]}),
    ]
    add_fieldsets = [(None, {"fields": ["phone", "full_name", "role", "department", "password1", "password2"]})]
