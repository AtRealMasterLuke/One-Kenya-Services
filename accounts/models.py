from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    CITIZEN = "citizen", "Citizen"
    OFFICER = "officer", "County officer"
    ADMIN = "admin", "Administrator"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.update(role=Role.ADMIN, is_staff=True, is_superuser=True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Citizens sign in with their phone number, the identifier the county reaches them on."""

    phone = models.CharField("phone number", max_length=32, unique=True)
    full_name = models.CharField(max_length=120)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CITIZEN)
    # Officers work for one department and only see that department's queue.
    department = models.ForeignKey(
        "requests_app.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="officers"
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can sign in to the Django admin.")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(role="officer") | models.Q(department__isnull=False),
                name="officer_has_department",
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    @property
    def is_citizen(self):
        return self.role == Role.CITIZEN

    @property
    def is_county_staff(self):
        return self.role in {Role.OFFICER, Role.ADMIN}
