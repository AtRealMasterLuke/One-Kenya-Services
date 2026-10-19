from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("requests/", views.my_requests, name="my_requests"),
    path("requests/new/", views.request_new, name="request_new"),
    path("requests/new/details/", views.request_new_details, name="request_new_details"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/<int:pk>/photo/", views.request_photo, name="request_photo"),
    path("requests/<int:pk>/action/", views.request_action, name="request_action"),
    path("requests/<int:pk>/follow/", views.request_follow, name="request_follow"),
    path("account/api-keys/", views.api_keys, name="api_keys"),
    path("staff/", views.staff_queue, name="staff_queue"),
    path("staff/analytics/", views.staff_analytics, name="staff_analytics"),
]
