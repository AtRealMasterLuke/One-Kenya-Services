# The replay dataset

There is no open dataset of Murang'a service complaints. To have real-world volumes, timings and
outcomes to design against (and to test against), the app replays a week of real municipal
complaints from **NYC 311** into Murang'a.

## Source

* Dataset: [311 Service Requests from 2010 to Present](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9), NYC Open Data (no restrictions on use).
* Query: created 2025-03-01 00:00 to 2025-03-08 00:00; complaint types *Street Light Condition, Water System, Sewer, Missed Collection, Dirty Condition, Street Condition, Illegal Dumping*; latitude present.
* Fetched 2026-10-19: **6,167 rows**, saved unchanged as `data/raw/nyc311_2025-03-01_to_2025-03-07.csv`.

## What the raw data decided

The categories on the report form come from what people actually complain about, not a
made-up list. The most common descriptors in the sample:

| Rows | NYC complaint (descriptor) | Murang'a category |
|---:|---|---|
| 975 + 631 + 96 | Dirty Condition (Trash); Illegal Dumping (Removal Request, Chronic Dumping) | Illegal dumping or litter |
| 783 + 134 + 55 + 42 | Street Condition (Pothole, Cave-in, Failed Street Repair, Rough/Pitted) | Pothole or damaged road |
| 496 + … | Street Light Condition (all) | Streetlight not working |
| 293 + 123 + 119 + … | Missed Collection (all) | Missed garbage collection |
| 289 + 136 + 130 + 49 | Water System (Leak, Hydrant Running/Leaking) | Water leak |
| 217 + 94 + 22 | Sewer (Backup, Catch Basin Clogged, Manhole Overflow) | Blocked or overflowing sewer |
| 131 | Water System (Possible Water Main Break) | Burst water main |
| 60 + 33 | Water System (No Water, Low Pressure) | No water or low pressure |

The water categories are split the way the **MUWASCO charter** splits its targets (leaks 12
working hours, burst mains 25 hours, sewer blockages 12 hours, no water 24 working hours), so
each category has one deadline. Descriptors with no Murang'a equivalent (plate condition,
blocked by construction, dirty water, basement flooding…) are left unmapped: 661 rows.

## Rules

The rules are written down in `data/replay_rules.json`, and both implementations follow them:

1. Look up (complaint type, descriptor). An exact descriptor match wins over `*`. No match: skip as *unmapped*.
2. Map status: Open/Pending → pending; Assigned/Started/In Progress → in_progress; Closed → closed.
3. A closed row needs closed date ≥ created date, otherwise skip as *bad dates*. (None in this sample.)
4. Map NYC's bounding box linearly onto Murang'a's (from the IEBC ward extent). The real
   clustering of complaints is kept. A point that lands in no ward is skipped as
   *outside county*, the same rule the live form applies.
5. Timestamps are NYC wall-clock times, read as Nairobi wall-clock times, so the
   office-hours pattern of real complaints lines up with Murang'a working hours.
6. History: pending at creation; in_progress at creation if the case was ever worked on;
   resolved, then closed, at the closed date.
7. Deadlines are computed by the app's own rules from the category target.

## Result

```
{"loaded": 3654, "outside_county": 1852, "unmapped": 661}
```

The loaded cases spread over 27 of the 35 wards. Every row goes through the real code path:
the ward lookup, duplicate detection, charter deadline, state machine, history and
database triggers.

## Limits

* The places are synthetic: NYC's geography squeezed into Murang'a's bounding box. The ward
  breakdown shows how the dashboard behaves, not where Murang'a's problems really are.
* NYC's resolution times reflect NYC's crews, not a Kenyan county's.
* The open dataset records only creation and closure, so the time a case spent "in progress"
  isn't known.
