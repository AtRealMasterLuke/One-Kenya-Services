"""
Ward routing and duplicate detection, checked against sources the boundaries weren't made from.
"""

import csv
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone

from requests_app import services
from requests_app.geo import make_point, possible_duplicates, ward_for
from requests_app.models import Category, Status, Ward

DATA = Path(__file__).resolve().parent.parent / "data"
KNOWN_POINTS = list(csv.DictReader(open(DATA / "known_points.csv", encoding="utf-8")))


@pytest.mark.django_db
def test_all_35_wards_in_7_constituencies():
    assert Ward.objects.count() == 35
    assert set(Ward.objects.values_list("constituency", flat=True)) == {
        "Gatanga", "Kandara", "Kangema", "Kigumo", "Kiharu", "Maragwa", "Mathioya"}


@pytest.mark.django_db
@pytest.mark.parametrize("row", KNOWN_POINTS, ids=[r["place"] for r in KNOWN_POINTS])
def test_known_places_route_to_their_ward(row):
    """data/known_points.csv: GeoNames places named after a ward (selection rule in
    scripts/build_known_points.py). Kagunduini's GeoNames point lies outside Kagundu-ini in all
    four boundary files compared (docs/boundaries.md), so the gazetteer, not the routing, is the
    likely error; it stays in the file and is marked as an expected failure."""
    if row["observed_discrepancy"]:
        pytest.xfail(f"gazetteer point disputed: {row['observed_discrepancy']}")
    ward = ward_for(make_point(row["latitude"], row["longitude"]))
    assert ward is not None and ward.code == row["expected_ward_code"], f"{row['place']} routed to {ward}"


@pytest.mark.django_db
def test_gazetteer_constituencies_agree_with_iebc_constituency_map():
    """Every GeoNames point in Murang'a: does the ward we route it to belong to the constituency
    the separately published IEBC/HDX constituency map puts it in? Measured 90.5% when the IEBC
    ward file was chosen (docs/evidence/ward_source_comparison.txt); fail if routing gets worse."""
    hdx = json.loads((DATA / "boundaries/muranga_constituencies_iebc_hdx.geojson").read_text(encoding="utf-8"))
    constituencies = [(f["properties"]["adm2_name"], GEOSGeometry(json.dumps(f["geometry"]), srid=4326)) for f in hdx["features"]]
    agree = total = 0
    for line in (DATA / "raw/geonames_KE_muranga.tsv").read_text(encoding="utf-8").splitlines():
        r = line.split("\t")
        if r[6] not in ("P", "S"):
            continue
        p = make_point(r[4], r[5])
        ward = ward_for(p)
        truth = next((name for name, g in constituencies if g.contains(p)), None)
        if ward and truth:
            total += 1
            agree += ward.constituency == truth
    assert total > 500
    assert agree / total >= 0.90, f"only {agree}/{total} agree"


@pytest.mark.django_db
@pytest.mark.parametrize("lat,lon,place", [
    (-1.2864, 36.8172, "Nairobi CBD"),
    (-0.4167, 36.9500, "Nyeri town"),
    (-0.5310, 37.4500, "Embu town"),
])
def test_outside_county_is_refused(citizen, lat, lon, place):
    with pytest.raises(services.OutsideCounty):
        services.create_request(citizen=citizen, category=Category.objects.get(code="streetlight"),
                                point=make_point(lat, lon), description="Should be refused")


def _offset(point, metres_north):
    return make_point(point.y + metres_north / 111_320, point.x)


@pytest.mark.django_db
class TestDuplicates:
    def test_same_problem_nearby_is_flagged(self, make_request, other_citizen, point_in):
        first = make_request("streetlight")
        second = make_request("streetlight", owner=other_citizen, point=_offset(point_in, 60))
        assert second.suspected_duplicate == first

    def test_just_outside_radius_is_not(self, make_request, other_citizen, point_in, settings):
        make_request("streetlight")
        second = make_request("streetlight", owner=other_citizen,
                              point=_offset(point_in, settings.DUPLICATE_RADIUS_METRES + 15))
        assert second.suspected_duplicate is None

    def test_different_problem_same_spot_is_not(self, make_request, other_citizen):
        make_request("streetlight")
        assert make_request("water_leak", owner=other_citizen).suspected_duplicate is None

    def test_old_reports_are_not(self, make_request, other_citizen, settings):
        long_ago = timezone.now() - timedelta(days=settings.DUPLICATE_WINDOW_DAYS + 1)
        make_request("streetlight", created_at=long_ago)
        assert make_request("streetlight", owner=other_citizen).suspected_duplicate is None

    def test_resolved_reports_are_not(self, make_request, other_citizen, roads_officer):
        first = make_request("streetlight")
        services.transition(first, Status.IN_PROGRESS, roads_officer)
        services.transition(first, Status.RESOLVED, roads_officer, note="New bulb")
        # The light failing again after a fix is a new fault, not a duplicate.
        assert make_request("streetlight", owner=other_citizen).suspected_duplicate is None

    def test_nearest_is_offered_first(self, make_request, point_in):
        far = make_request("streetlight", point=_offset(point_in, 80))
        near = make_request("streetlight", point=_offset(point_in, 10))
        found = list(possible_duplicates(Category.objects.get(code="streetlight"), point_in, timezone.now()))
        assert found[:2] == [near, far]
        assert found[0].distance.m == pytest.approx(10, abs=1)

    def test_ward_only_reports_never_count_as_duplicates(self, citizen, other_citizen, township):
        streetlight = Category.objects.get(code="streetlight")
        first = services.create_request(citizen=citizen, category=streetlight, ward=township, description="Ward only one")
        second = services.create_request(citizen=other_citizen, category=streetlight, ward=township, description="Ward only two")
        assert first.location_approximate and second.suspected_duplicate is None


def test_known_points_file_follows_its_rule():
    """Guard against hand-editing: every row must still satisfy the selection rule."""
    def rounded(x):
        return abs(x * 60 - round(x * 60)) < 0.02

    for row in KNOWN_POINTS:
        assert not rounded(float(row["latitude"])) and not rounded(float(row["longitude"]))
        assert re.sub(r"[^a-z]", "", row["place"].lower()) == re.sub(r"[^a-z]", "", row["expected_ward"].split("/")[0].lower())
