"""
Build data/known_points.csv from the GeoNames gazetteer, by a rule fixed before looking at
any results (see docs/boundaries.md):

  a populated place (feature class P) whose name matches a ward's name, that appears once
  in Murang'a, and whose coordinates are not rounded to a whole arc-minute (~1.8 km).

Run inside the app container:  python manage.py shell < scripts/build_known_points.py
"""

import csv
import re
from collections import Counter

from requests_app.geo import make_point, ward_for
from requests_app.models import Ward


def norm(s):
    return re.sub(r"[^a-z]", "", s.lower())


def rounded(x):
    return abs(x * 60 - round(x * 60)) < 0.02


rows = [l.split("\t") for l in open("data/raw/geonames_KE_muranga.tsv", encoding="utf-8").read().splitlines()]
ppl = [r for r in rows if r[6] == "P"]
names = Counter(norm(r[1]) for r in ppl)
out = []
for w in Ward.objects.order_by("code"):
    base = norm(w.name.split("/")[0])
    for r in ppl:
        lat, lon = float(r[4]), float(r[5])
        if norm(r[1]) == base and names[base] == 1 and not (rounded(lat) or rounded(lon)):
            p = make_point(lat, lon)
            got = ward_for(p)
            note = "" if got == w else f"falls in {got.name}, {w.shape.distance(p) * 111320:.0f} m outside {w.name}"
            out.append([r[1], r[0], lat, lon, w.name, w.code, w.constituency, note])

with open("data/known_points.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["place", "geonames_id", "latitude", "longitude", "expected_ward", "expected_ward_code",
                     "expected_constituency", "observed_discrepancy"])
    writer.writerows(out)
print(open("data/known_points.csv", encoding="utf-8").read())
