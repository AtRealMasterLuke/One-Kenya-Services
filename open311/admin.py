from django.contrib import admin

from .models import ApiKey


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "prefix", "created_at", "last_used_at", "revoked_at"]
    readonly_fields = ["prefix", "digest", "created_at", "last_used_at"]
