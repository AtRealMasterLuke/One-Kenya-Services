import itertools

import pytest
from django.core.management import call_command

from accounts.models import Role, User
from requests_app import services
from requests_app.models import Category, Department, Ward

PASSWORD = "test-password-123"
_phones = itertools.count(1)


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Real Murang'a wards for every test (loaded once per session)."""
    with django_db_blocker.unblock():
        call_command("load_wards", verbosity=0)


@pytest.fixture(autouse=True)
def _no_real_sms(settings):
    settings.AT_API_KEY = ""


def _phone():
    return f"+2547{next(_phones):08d}"


@pytest.fixture
def make_user(db):
    def make(role=Role.CITIZEN, department=None, **extra):
        return User.objects.create_user(
            phone=_phone(), password=PASSWORD, full_name=f"Test {role}", role=role, department=department, **extra
        )

    return make


@pytest.fixture
def citizen(make_user):
    return make_user()


@pytest.fixture
def other_citizen(make_user):
    return make_user()


@pytest.fixture
def water_officer(make_user):
    return make_user(Role.OFFICER, Department.objects.get(code="water"))


@pytest.fixture
def roads_officer(make_user):
    return make_user(Role.OFFICER, Department.objects.get(code="roads"))


@pytest.fixture
def admin_user(make_user):
    return make_user(Role.ADMIN)


@pytest.fixture
def township():
    """Murang'a town's ward."""
    return Ward.objects.get(name="Township")


@pytest.fixture
def point_in(township):
    return township.shape.representative_point()


@pytest.fixture
def make_request(db, citizen, point_in):
    def make(category="water_leak", owner=None, point=None, **extra):
        return services.create_request(
            citizen=owner or citizen,
            category=Category.objects.get(code=category),
            point=point or point_in,
            description="A test report with enough words.",
            **extra,
        )

    return make


@pytest.fixture(autouse=True)
def _plain_static_storage(settings):
    """Tests run with DEBUG off, where the hashed storage needs a collectstatic manifest."""
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
