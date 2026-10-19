from django.urls import path, re_path

from . import views

FMT = r"\.(?P<fmt>json|xml)$"

urlpatterns = [
    path("discovery.json", views.discovery, name="open311_discovery"),
    re_path(r"^v2/services" + FMT, views.service_list, name="open311_services"),
    re_path(r"^v2/services/(?P<code>[\w-]+)" + FMT, views.service_definition, name="open311_service"),
    re_path(r"^v2/requests" + FMT, views.request_list, name="open311_requests"),
    re_path(r"^v2/requests/(?P<pk>\d+)" + FMT, views.request_detail, name="open311_request"),
]
