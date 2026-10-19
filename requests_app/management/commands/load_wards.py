"""
Load Murang'a's 35 county assembly wards.

Source: IEBC ward boundaries (2012 delimitation, still in force), as published on HDX in the
"Kenya Admin Boundaries - Election Polling stations" dataset. Chosen over GADM 4.1, the
American Red Cross 2016 file and FAO 2016 because it agrees best with an independent
reference; see docs/boundaries.md and scripts/compare_ward_sources.py.

The redistribution terms aren't stated, so the file isn't in the repository: the first run
downloads it, keeps only Murang'a, and caches it in data/boundaries/.
"""

import io
import json
import math
import zipfile
from pathlib import Path

import requests
import shapefile  # pyshp: pure-Python shapefile reader, no GDAL needed
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from shapely.geometry import mapping, shape
from shapely.ops import transform

from requests_app.geo import clear_ward_cache
from requests_app.models import Ward

IEBC_WARDS_URL = (
    "https://data.humdata.org/dataset/4da920dc-c1dc-4889-b06c-66ecb65e2b94/resource/"
    "e77739a3-c921-4690-8d3b-62249e26324e/download/ward.results.zip"
)
WARDS_FILE = Path(settings.BASE_DIR) / "data" / "boundaries" / "muranga_wards_iebc2012.geojson"
EXPECTED_WARDS = 35
# The IEBC file's .prj declares Mercator (variant B) on the WGS84 *ellipsoid*, so the inverse
# needs the ellipsoidal formula; the spherical "web Mercator" one is off by ~600 m at Murang'a.
WGS84_A = 6378137.0
WGS84_E = math.sqrt(2 / 298.257223563 - (1 / 298.257223563) ** 2)


def mercator_to_lonlat(x, y, z=None):
    t = math.exp(-y / WGS84_A)
    lat = math.pi / 2 - 2 * math.atan(t)
    for _ in range(10):  # converges to well under a millimetre in a few steps
        esin = WGS84_E * math.sin(lat)
        lat = math.pi / 2 - 2 * math.atan(t * ((1 - esin) / (1 + esin)) ** (WGS84_E / 2))
    return math.degrees(x / WGS84_A), math.degrees(lat)


def tidy(name):
    """IEBC writes names in capitals: KAGUNDU-INI -> Kagundu-ini, NG'ARARIA -> Ng'araria."""
    return name.title().replace("-Ini", "-ini").replace("'A", "'a")


def download_wards():
    resp = requests.get(IEBC_WARDS_URL, timeout=300)
    resp.raise_for_status()
    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    base = "ward.results.formatted"
    reader = shapefile.Reader(
        shp=io.BytesIO(archive.read(f"{base}.shp")),
        shx=io.BytesIO(archive.read(f"{base}.shx")),
        dbf=io.BytesIO(archive.read(f"{base}.dbf")),
        encoding="latin-1",
    )
    features = []
    for record in reader.iterShapeRecords():
        props = record.record.as_dict()
        if not (props.get("COUNTY_NAM") or "").upper().startswith("MURANG"):
            continue
        geom = transform(mercator_to_lonlat, shape(record.shape.__geo_interface__))
        features.append({
            "type": "Feature",
            "properties": {
                "code": f"{int(props['COUNTY_ASS']):04d}",
                "name": tidy(props["NAME"]),
                "constituency": props["CONSTITUEN"].title(),
            },
            "geometry": mapping(geom),
        })
    WARDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WARDS_FILE.write_text(json.dumps({
        "type": "FeatureCollection",
        "_source": f"IEBC ward boundaries via HDX, filtered to Murang'a. {IEBC_WARDS_URL}",
        "features": features,
    }), encoding="utf-8")


class Command(BaseCommand):
    help = "Load Murang'a ward boundaries (downloads the IEBC file on first run)."

    def handle(self, *args, **options):
        if not WARDS_FILE.exists():
            self.stdout.write("Downloading IEBC ward boundaries…")
            download_wards()
        features = json.loads(WARDS_FILE.read_text(encoding="utf-8"))["features"]
        if len(features) != EXPECTED_WARDS:
            raise CommandError(f"Expected {EXPECTED_WARDS} Murang'a wards, found {len(features)} in {WARDS_FILE}")
        for feature in features:
            props = feature["properties"]
            Ward.objects.update_or_create(
                code=props["code"],
                defaults={"name": props["name"], "constituency": props["constituency"], "boundary": feature["geometry"]},
            )
        clear_ward_cache()
        self.stdout.write(self.style.SUCCESS(f"{Ward.objects.count()} wards loaded."))
