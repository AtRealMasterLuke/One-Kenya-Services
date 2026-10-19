"""
Ward lookup and duplicate search in plain Python (shapely), so the app runs anywhere that can
pip-install its requirements, including Vercel, without GDAL or PostGIS.

There are only 35 ward polygons, so they're loaded once per process and checked in memory.
"""

from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from django.conf import settings
from shapely.geometry import Point
from shapely.prepared import prep

from .models import OPEN_STATUSES, ServiceRequest, Ward

EARTH_RADIUS_M = 6_371_008.8
_ward_cache = None


def make_point(latitude, longitude):
    """A shapely point: x is longitude, y is latitude."""
    return Point(float(longitude), float(latitude))


def clear_ward_cache():
    global _ward_cache
    _ward_cache = None


def _wards():
    global _ward_cache
    if _ward_cache is None:
        _ward_cache = [(ward, prep(ward.shape)) for ward in Ward.objects.all()]
    return _ward_cache


def ward_for(point):
    """The ward containing a point, or None if it is outside Murang'a County."""
    return next((ward for ward, polygon in _wards() if polygon.contains(point)), None)


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (haversine)."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def possible_duplicates(category, point, at, exclude_pk=None):
    """Open reports of the same problem within DUPLICATE_RADIUS_METRES, made in the
    DUPLICATE_WINDOW_DAYS before `at`, nearest first. Each result has `.distance_m`."""
    radius = settings.DUPLICATE_RADIUS_METRES
    # Cheap bounding-box filter in SQL, exact distance in Python.
    dlat = radius / 111_000
    dlon = dlat / max(cos(radians(point.y)), 0.01)
    qs = ServiceRequest.objects.filter(
        category=category,
        status__in=OPEN_STATUSES,
        location_approximate=False,
        created_at__gte=at - timedelta(days=settings.DUPLICATE_WINDOW_DAYS),
        created_at__lte=at,
        latitude__range=(point.y - dlat, point.y + dlat),
        longitude__range=(point.x - dlon, point.x + dlon),
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    found = []
    for req in qs.select_related("category"):
        req.distance_m = distance_m(point.y, point.x, req.latitude, req.longitude)
        if req.distance_m <= radius:
            found.append(req)
    return sorted(found, key=lambda r: (r.distance_m, r.created_at))
