# Ward boundaries: which file, and how we know it's right

Ward routing decides which officer sees a report, so the boundary file is the single most
consequential piece of data in the system. It was chosen by measurement, not by convenience.

## Candidates

| Source | Notes |
|---|---|
| GADM 4.1, level 3 | Widely used; licence forbids redistribution. Picked first. |
| American Red Cross 2016 (HDX) | "Topology cleaned", used with Kenya's DHIS2 health system; labels wards by sub-county. CC BY. |
| **IEBC 2012 (HDX "kenya-elections")** | From vote.iebc.or.ke, published by the body that draws the wards. Redistribution terms not stated. |
| FAO 2016 (HDX) | Digitised from IEBC PDF maps. |

## Independent references

Neither reference was used to make any of the candidates:

* **A. IEBC constituency polygons** (HDX *Kenya – Subnational Administrative Boundaries*, valid 2019).
* **B. The GeoNames gazetteer**: 791 named places in Murang'a (`data/raw/geonames_KE_muranga.tsv`).

## Measurements

From `scripts/compare_ward_sources.py`, saved in `docs/evidence/ward_source_comparison.txt`:

| Source | Wards | Area (km²) | A: ward area inside its own constituency | B: gazetteer points in the right constituency | Namesake places in their ward |
|---|---:|---:|---:|---:|---:|
| GADM 4.1 | 35 | 2,543 | 88.7% | 86.7% (442/510) | 8/9 |
| American Red Cross 2016 | 35 | 2,575 | 85.1% | 88.8% (460/518) | 8/9 |
| **IEBC 2012** | **35** | **2,555** | **92.4%** | **90.5% (467/516)** | **8/9** |
| FAO 2016 | 26 | 1,934 | n/a | n/a | 6/7 |

Murang'a's official area is about 2,558 km². **IEBC 2012 is best on every measure**, and it is the
authoritative source, so it is the one the app uses. `manage.py load_wards` downloads it on
first run, because its redistribution terms aren't stated.

The first choice, GADM, put about 1 in 7 gazetteer places in the wrong constituency, some of
them 4.7 km from any border. Without this check, that would have shipped.

## The known-points test file

`data/known_points.csv` comes from GeoNames by a rule fixed *before* looking at any
results (`scripts/build_known_points.py`): a populated place that shares a ward's name, is
listed only once in Murang'a, and has coordinates that aren't rounded to a whole arc-minute
(about 1.8 km).

That gives 9 places. 8 route to their namesake ward. **Kagunduini** (GeoNames 195498) lands
1,059 m outside Kagundu-ini ward, in Kahumbu, and it lands outside Kagundu-ini in *all four*
boundary files, which points at the gazetteer coordinate rather than the routing. It stays in
the file, marked as an expected failure (`xfail(strict)`), so the test suite will notice if
that ever changes.

`tests/test_geo.py` also re-runs measurement B on every test run and fails if agreement
drops below 90%.

## What remains uncertain

Around 1 in 10 gazetteer points still fall in a different constituency than the 2019 HDX
polygons say. Some of that is gazetteer error and some is the two boundary files
disagreeing near borders. A report filed close to a ward border may go to the
neighbouring ward's queue. The officer can still see the exact pin on the map. The real fix
is the county's own current GIS layer.
