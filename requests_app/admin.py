from django.contrib import admin

from .models import CaseEvent, Category, Department, Notification, ServiceRequest, Ward


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "calendar", "escalation_phone"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "department", "sla_hours", "sla_basis", "sla_is_assumed"]


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ["name", "constituency", "code"]
    exclude = ["boundary"]
    list_filter = ["constituency"]


class ReadOnlyEvents(admin.TabularInline):
    model = CaseEvent
    extra = 0
    can_delete = False
    readonly_fields = ["kind", "from_status", "to_status", "actor", "actor_role", "note", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    """Read-only here: status changes must go through the app so they are checked and logged."""

    list_display = ["reference", "category", "ward", "status", "created_at", "due_at", "source"]
    list_filter = ["status", "category", "source", "ward__constituency"]
    inlines = [ReadOnlyEvents]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["phone", "state", "attempts", "created_at", "sent_at"]
    list_filter = ["state"]
    readonly_fields = [f.name for f in Notification._meta.fields]
