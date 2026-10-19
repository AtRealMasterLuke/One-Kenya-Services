import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def _digest(key):
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKeyManager(models.Manager):
    def issue(self, user, name="Open311 client"):
        """Create a key and return (ApiKey, plaintext). The plaintext is shown once and never stored."""
        plaintext = secrets.token_urlsafe(32)
        key = self.create(user=user, name=name, prefix=plaintext[:8], digest=_digest(plaintext))
        return key, plaintext

    def authenticate(self, plaintext):
        if not plaintext:
            return None
        key = (
            self.filter(digest=_digest(plaintext), revoked_at__isnull=True, user__is_active=True)
            .select_related("user")
            .first()
        )
        if key:
            self.filter(pk=key.pk).update(last_used_at=timezone.now())
        return key


class ApiKey(models.Model):
    """A citizen's personal key, so an Open311 app can file reports in their name."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=60)
    prefix = models.CharField(max_length=8)
    digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = ApiKeyManager()

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"
