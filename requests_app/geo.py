from datetime import timedelta

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from .models import OPEN_STATUSES, ServiceRequest, Ward


def make_point(latitude, longitude):
    return Point(float(longitude), float(latitude), srid=4326)


def ward_for(point):
    """The ward containing a point, or None if it is outside Murang'a County."""
    return Ward.objects.filter(geom__contains=point).first()


def possible_duplicates(category, point, at, exclude_pk=None):
    """Open reports of the same problem within DUPLICATE_RADIUS_METRES, made in the
    DUPLICATE_WINDOW_DAYS before `at`, nearest first."""
    window_start = at - timedelta(days=settings.DUPLICATE_WINDOW_DAYS)
    qs = (
        ServiceRequest.objects.filter(
            category=category,
            status__in=OPEN_STATUSES,
            location_approximate=False,
            created_at__gte=window_start,
            created_at__lte=at,
            location__dwithin=(point, D(m=settings.DUPLICATE_RADIUS_METRES)),
        )
        .annotate(distance=Distance("location", point))
        .order_by("distance", "created_at")
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs
