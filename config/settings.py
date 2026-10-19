"""
Django settings for the Murang'a County service request system.

Everything that differs between a laptop and the deployed site is read from the
environment, so the same image runs in both places.
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, "1" if default else "0").lower() in {"1", "true", "yes"}


DEBUG = env_bool("DJANGO_DEBUG")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("insecure-dev-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off")

ON_VERCEL = bool(os.environ.get("VERCEL"))
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in {"localhost", "127.0.0.1"}]
if ON_VERCEL:
    ALLOWED_HOSTS.append(".vercel.app")
    CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.forms",
    "axes",
    "accounts",
    "requests_app",
    "open311",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.SecurityHeadersMiddleware",  # above WhiteNoise so static files get the headers too
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

FORM_RENDERER = "config.forms.FormRenderer"

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default="postgres://kenyamoja:kenyamoja@localhost:5432/kenyamoja",
        conn_max_age=0 if ON_VERCEL else 60,  # serverless functions shouldn't hold connections open
    )
}


AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# Lock an account+IP pair out for 15 minutes after 5 failed logins (ASVS 2.2.1).
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.25
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_USERNAME_CALLABLE = "accounts.forms.username_for_lockout"
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "axes/lockout.html"


LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = None if ON_VERCEL else BASE_DIR / "staticfiles"  # no collectstatic on Vercel
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Vercel has no collectstatic step, so there WhiteNoise serves straight from static/.
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if ON_VERCEL
                    else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = ON_VERCEL

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Photos are re-encoded and stored in the database, so uploads only need to fit in memory.
# Vercel caps request bodies at 4.5 MB.
DATA_UPLOAD_MAX_MEMORY_SIZE = 4_500_000
FILE_UPLOAD_MAX_MEMORY_SIZE = 4_500_000


# Security headers. HTTPS-only settings switch on outside DEBUG.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True  # no JavaScript reads the token; forms carry it
SESSION_COOKIE_AGE = 60 * 60 * 8
WHITENOISE_ALLOW_ALL_ORIGINS = False  # static files are only used by our own pages
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    # DJANGO_SECURE_COOKIES=0 only for the plain-HTTP audit container (docker-compose web-prod).
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]


# Case-handling rules. See docs/decisions.md for why these values.
DUPLICATE_RADIUS_METRES = 100
DUPLICATE_WINDOW_DAYS = 14
AUTO_CLOSE_RESOLVED_AFTER_DAYS = 7

# Africa's Talking. With no API key, messages are logged and marked "skipped".
AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY", "")
AT_SENDER_ID = os.environ.get("AT_SENDER_ID", "")
SITE_URL = os.environ.get("SITE_URL") or (
    f"https://{os.environ['VERCEL_PROJECT_PRODUCTION_URL']}" if os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")
    else "http://localhost:8000"
)
# Vercel Cron sends "Authorization: Bearer <CRON_SECRET>" to /cron/maintenance.
CRON_SECRET = os.environ.get("CRON_SECRET", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
