from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("healthz", lambda request: HttpResponse("ok", content_type="text/plain"), name="healthz"),
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("open311/", include("open311.urls")),
    path("", include("requests_app.urls")),
]
