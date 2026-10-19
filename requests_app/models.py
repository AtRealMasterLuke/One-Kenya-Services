from functools import cached_property

from django.conf import settings
from django.db import models
from django.utils import timezone
from shapely.geometry import Point, shape


class Status(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"
    MERGED = "merged", "Merged into another report"


OPEN_STATUSES = (Status.PENDING, Status.IN_PROGRESS)
DONE_STATUSES = (Status.RESOLVED, Status.CLOSED)


class Department(models.Model):
    class Calendar(models.TextChoices):
        MUWASCO = "muwasco", "MUWASCO working hours"
        COUNTY = "county", "County office hours"

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    calendar = models.CharField(max_length=16, choices=Calendar.choices)
    escalation_phone = models.CharField(
        max_length=16, blank=True, help_text="Supervisor number that receives SMS when a case becomes overdue."
    )

    def __str__(self):
        return self.name


class Ward(models.Model):
    code = models.CharField(max_length=32, unique=True, help_text="IEBC county assembly ward code, e.g. 0525")
    name = models.CharField(max_length=80)
    constituency = models.CharField(max_length=80)
    boundary = models.JSONField(help_text="GeoJSON (Multi)Polygon in WGS84 longitude/latitude")

    class Meta:
        ordering = ["constituency", "name"]

    def __str__(self):
        return f"{self.name} ({self.constituency})"

    @cached_property
    def shape(self):
        return shape(self.boundary)


class Category(models.Model):
    class Basis(models.TextChoices):
        CLOCK = "clock", "Clock hours"
        WORKING = "working", "Working hours"

    code = models.SlugField(unique=True, help_text="Open311 service_code")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="categories")
    sla_hours = models.PositiveIntegerField()
    sla_basis = models.CharField(max_length=8, choices=Basis.choices)
    sla_is_assumed = models.BooleanField()
    sla_source = models.TextField()
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    @property
    def target_label(self):
        unit = "working hours" if self.sla_basis == self.Basis.WORKING else "hours"
        return f"{self.sla_hours} {unit}"


class ServiceRequest(models.Model):
    class Source(models.TextChoices):
        WEB = "web", "Website"
        OPEN311 = "open311", "Open311 API"
        REPLAY = "replay", "Dataset replay"

    citizen = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="service_requests")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="requests")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="requests")
    latitude = models.FloatField()
    longitude = models.FloatField()
    location_approximate = models.BooleanField(
        default=False, help_text="Reporter chose a ward instead of a point; location is the ward's centre."
    )
    landmark = models.CharField(max_length=200, blank=True, help_text="Nearby landmark, e.g. 'opposite Mukuyu market'")
    description = models.TextField(max_length=2000)

    # Status is only ever changed through requests_app.services.transition(); a database
    # trigger rejects any other status change (see migration 0002).
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    due_at = models.DateTimeField(help_text="Charter deadline, fixed when the report is made.")
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="Latest resolution; cleared on reopen.")
    closed_at = models.DateTimeField(null=True, blank=True)

    escalation_level = models.PositiveSmallIntegerField(default=0)
    suspected_duplicate = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Nearest open report of the same category found when this one was made.",
    )
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="merged_cases")

    source = models.CharField(max_length=8, choices=Source.choices, default=Source.WEB)
    external_ref = models.CharField(max_length=40, blank=True, help_text="ID in the source dataset, for replays.")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "due_at"]),
            models.Index(fields=["ward", "category"]),
            models.Index(fields=["category", "latitude", "longitude"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status="merged", merged_into__isnull=False)
                | (~models.Q(status="merged") & models.Q(merged_into__isnull=True)),
                name="merged_iff_merged_into",
            ),
            models.UniqueConstraint(
                fields=["source", "external_ref"], condition=~models.Q(external_ref=""), name="unique_external_ref"
            ),
        ]

    def __str__(self):
        return f"{self.reference} {self.category}"

    @property
    def reference(self):
        return f"MUR-{self.pk:06d}" if self.pk else "MUR-new"

    @property
    def point(self):
        return Point(self.longitude, self.latitude)

    @property
    def is_open(self):
        return self.status in OPEN_STATUSES

    def is_overdue(self, now=None):
        return self.is_open and self.due_at < (now or timezone.now())


class Photo(models.Model):
    """Re-encoded upload, EXIF removed. Stored in the database so it survives redeploys and is
    only ever served through a view that checks who is asking."""

    request = models.OneToOneField(ServiceRequest, on_delete=models.CASCADE, related_name="photo")
    data = models.BinaryField()
    content_type = models.CharField(max_length=32)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now)


class CaseEvent(models.Model):
    """Append-only case history. A trigger rejects UPDATE and DELETE (see migration 0002)."""

    class Kind(models.TextChoices):
        STATUS = "status", "Status change"
        ESCALATION = "escalation", "Escalation"
        MERGE = "merge", "Duplicate merged in"
        FOLLOW = "follow", "Citizen followed"

    request = models.ForeignKey(ServiceRequest, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    actor_role = models.CharField(max_length=16, help_text="owner, officer, admin or system, as at the time")
    note = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["request", "kind", "created_at"])]


class Follower(models.Model):
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="followers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followed_requests")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["request", "user"], name="unique_follower")]


class Notification(models.Model):
    """SMS outbox. Rows are written in the same transaction as the status change and sent
    after commit; anything that fails is retried by `run_case_maintenance`."""

    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped (no SMS provider configured)"

    request = models.ForeignKey(ServiceRequest, null=True, on_delete=models.SET_NULL, related_name="notifications")
    phone = models.CharField(max_length=16)
    message = models.CharField(max_length=320)
    state = models.CharField(max_length=8, choices=State.choices, default=State.QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    provider_response = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
