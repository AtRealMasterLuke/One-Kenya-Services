"""
Load Murang'a's 35 county assembly wards.

Source: IEBC ward boundaries (2012 delimitation, still in force), as published on HDX in the
"Kenya Admin Boundaries - Election Polling stations" dataset. Chosen over GADM 4.1, the
American Red Cross 2016 file and FAO 2016 because it agrees best with an independent
reference; see docs/boundaries.md and scripts/compare_ward_sources.py.

The redistribution terms aren't stated, so the file isn't in the repository: the first run
downloads it, keeps only Murang'a, and caches it in data/boundaries/.
"""

import json
import tempfile
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.gis.gdal import CoordTransform, DataSource, SpatialReference
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError

from requests_app.models import Ward

IEBC_WARDS_URL = (
    "https://data.humdata.org/dataset/4da920dc-c1dc-4889-b06c-66ecb65e2b94/resource/"
    "e77739a3-c921-4690-8d3b-62249e26324e/download/ward.results.zip"
)
WARDS_FILE = Path(settings.BASE_DIR) / "data" / "boundaries" / "muranga_wards_iebc2012.geojson"
EXPECTED_WARDS = 35


def tidy(name):
    """IEBC writes names in capitals: KAGUNDU-INI -> Kagundu-ini, NG'ARARIA -> Ng'araria."""
    return name.title().replace("-Ini", "-ini").replace("'A", "'a")


def download_wards():
    resp = requests.get(IEBC_WARDS_URL, timeout=300)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(resp.content)
    layer = DataSource(f"/vsizip/{tmp.name}/ward.results.formatted.shp")[0]
    to_wgs84 = CoordTransform(layer.srs, SpatialReference(4326))
    features = []
    for feature in layer:
        if not (feature["COUNTY_NAM"].value or "").upper().startswith("MURANG"):
            continue
        geom = feature.geom
        geom.transform(to_wgs84)
        features.append({
            "type": "Feature",
            "properties": {
                "code": f"{feature['COUNTY_ASS'].value:04d}",
                "name": tidy(feature["NAME"].value),
                "constituency": feature["CONSTITUEN"].value.title(),
            },
            "geometry": json.loads(geom.json),
        })
    Path(tmp.name).unlink()
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
            geom = GEOSGeometry(json.dumps(feature["geometry"]), srid=4326)
            if geom.geom_type == "Polygon":
                geom = MultiPolygon(geom, srid=4326)
            Ward.objects.update_or_create(
                code=props["code"],
                defaults={"name": props["name"], "constituency": props["constituency"], "geom": geom},
            )
        self.stdout.write(self.style.SUCCESS(f"{Ward.objects.count()} wards loaded."))
