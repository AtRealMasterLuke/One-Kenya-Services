"""
Which ward boundary file should route reports?

Ward routing decides which officer sees a case, so the boundary file has to be checked
against something it wasn't made from. Each candidate is scored against two independent
references:

  A. IEBC constituency polygons (HDX "Kenya - Subnational Administrative Boundaries", 2019).
     For every ward, the share of its area lying inside the constituency it claims to belong to.
  B. GeoNames gazetteer points in Murang'a (data/raw/geonames_KE_muranga.tsv).
     For every point, does the ward it falls in belong to the constituency HDX puts it in?
     Plus the strict namesake test: places that share a ward's name, are listed once,
     and have unrounded coordinates should fall in that ward.

Usage (inside the container, after downloading the candidates; see docs/boundaries.md):
  python scripts/compare_ward_sources.py
"""

import json
import re
from collections import Counter
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
DL = ROOT / "data" / "tmp_downloads"

CONSTITUENCIES = ["Gatanga", "Kandara", "Kangema", "Kigumo", "Kiharu", "Maragwa", "Mathioya"]
SUBCOUNTY_TO_CONSTITUENCY = {"muranga south": "Maragwa"}  # the Red Cross file names sub-counties


def norm(name):
    return re.sub(r"[^a-z]", "", name.lower().replace(" ward", ""))


def constituency_name(raw):
    raw = raw.lower().replace(" sub county", "").strip()
    if raw in SUBCOUNTY_TO_CONSTITUENCY:
        return SUBCOUNTY_TO_CONSTITUENCY[raw]
    return next(c for c in CONSTITUENCIES if c.lower() == raw)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def candidates():
    official = {norm(f["properties"]["NAME_3"]) for f in load(ROOT / "data/tmp_downloads/gadm/muranga_wards_gadm41.geojson")}
    yield "GADM 4.1", [
        (f["properties"]["NAME_3"], f["properties"]["NAME_2"], shape(f["geometry"]))
        for f in load(ROOT / "data/tmp_downloads/gadm/muranga_wards_gadm41.geojson")
    ]
    yield "American Red Cross 2016 (HDX)", [
        (f["properties"]["ward"].replace(" Ward", ""), constituency_name(f["properties"]["subcounty"]), shape(f["geometry"]))
        for f in load(DL / "arc/muranga.geojson")
    ]
    yield "IEBC 2012 (HDX kenya-elections)", [
        (f["properties"]["NAME"].title(), constituency_name(f["properties"]["CONSTITUEN"]), shape(f["geometry"]))
        for f in load(DL / "iebc/muranga.geojson")
    ]
    fao = []
    for f in load(DL / "fao/muranga.geojson"):
        name = f["properties"]["IEBC_WARDS"] or ""
        if norm(name) in official and f["properties"].get("FIRST_DIST", "").lower().startswith(("mura", "mara", "kand", "gata", "kang", "kigu", "math")):
            fao.append((name, None, shape(f["geometry"])))
    yield "FAO 2016 (HDX)", fao


def main():
    hdx = [(f["properties"]["adm2_name"], shape(f["geometry"])) for f in load(ROOT / "data/boundaries/muranga_constituencies_iebc_hdx.geojson")]
    hdx_by_name = dict(hdx)
    county = unary_union([g for _, g in hdx])
    rows = [l.split("\t") for l in (ROOT / "data/raw/geonames_KE_muranga.tsv").read_text(encoding="utf-8").splitlines()]
    points = [(r[1], Point(float(r[5]), float(r[4]))) for r in rows if r[6] in ("P", "S")]
    ppl = [r for r in rows if r[6] == "P"]
    counts = Counter(norm(r[1]) for r in ppl)

    def rounded(x):
        return abs(x * 60 - round(x * 60)) < 0.02

    print(f"{'source':34} wards  area_km2  A:area-in-own-constituency  B:gazetteer-agree  namesake")
    for label, wards in candidates():
        area = sum(g.area for _, _, g in wards) * 111.32 ** 2
        if wards and wards[0][1]:
            inside = sum(g.intersection(hdx_by_name[c]).area for _, c, g in wards) / sum(g.area for _, _, g in wards)
            agree = total = 0
            for _, p in points:
                ward = next((w for w in wards if w[2].contains(p)), None)
                truth = next((n for n, g in hdx if g.contains(p)), None)
                if ward and truth:
                    total += 1
                    agree += ward[1] == truth
            a_text, b_text = f"{inside:.1%}", f"{agree}/{total} ({agree / total:.1%})"
        else:
            a_text = b_text = "n/a (no constituency field)"
        ok = tried = 0
        for name, _, geom in wards:
            base = norm(name.split("/")[0])
            for r in ppl:
                lat, lon = float(r[4]), float(r[5])
                if norm(r[1]) == base and counts[base] == 1 and not (rounded(lat) or rounded(lon)):
                    tried += 1
                    ok += geom.contains(Point(lon, lat))
        coverage = unary_union([g for _, _, g in wards]).intersection(county).area / county.area if wards else 0
        print(f"{label:34} {len(wards):5}  {area:8.0f}  {a_text:27}  {b_text:17}  {ok}/{tried}   (covers {coverage:.1%} of county)")


if __name__ == "__main__":
    main()
