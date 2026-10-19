# Decisions and trade-offs

## Stack: Django + GeoDjango + PostGIS, server-rendered

* **PostGIS does the hard parts in the database.** Ward routing is `ST_Contains`. Duplicate
  search is `ST_DWithin` on a geography column (true metres, not degrees). GeoDjango exposes both
  without raw SQL.
* **Server-rendered HTML** keeps each page to a few kilobytes and working without JavaScript.
  That matters on 3G and on cheap Android phones. The only script is the location picker, and it
  only downloads the map library when someone asks for the map.
* **Django's built-ins** (auth, CSRF, sessions, admin, migrations, form validation) cover most of
  OWASP ASVS Level 1 without extra code.
* Rejected: a React SPA with an API. It would ship ~10× the JavaScript for the same forms, and
  everything would need building twice (the API and the UI's validation).

## The state machine is enforced twice

`requests_app/statemachine.py` holds the transition table. The service layer checks it on every
change, and a PostgreSQL trigger generated from the same table rejects any other status change,
including one made through the Django admin, a shell or a future bug. Case history
(`CaseEvent`) has a trigger that rejects UPDATE and DELETE, so it really is append-only.

**Merged** is a fifth, terminal status beyond the four in the brief. Merging a duplicate isn't a
resolution. Counting it as "closed" would inflate the resolution figures, and deleting it would
lose the reporter. A merged case's reporter and followers become followers of the surviving case.

**Resolved ≠ closed.** An officer marks a case resolved; the *citizen* confirms (closed) or
reopens it. If they don't respond within 7 days it closes automatically. Otherwise "time to
resolve" would measure how fast staff click a button.

## Deadlines are fixed at creation

`due_at` is set when the report is made and never moves. A reopened case keeps its original
deadline, because from the citizen's point of view the clock never stopped. "Working hours" use
MUWASCO's published opening hours or standard county hours and skip Kenyan public holidays
(`holidays` package).

## Duplicates: 100 m, 14 days, same category, still open

* **100 m** is roughly one streetlight span or a short block. Wider radii flag unrelated faults in
  dense areas (Murang'a town, Kenol).
* **14 days**: older open reports are better merged by an officer than proposed to a citizen.
* **Resolved cases are excluded**: a light failing again after a fix is a new fault.
* Citizens are shown possible duplicates *before* writing a description, and can follow one
  instead. The match is also stored as `suspected_duplicate`, so officers see a flag and can merge.

## Routing to departments, not people

Each category belongs to one department. Officers see only their department's queue. Ward-level
assignment to named staff was left out, as it's a staffing decision the county would make.
Known gap: MUWASCO's charter is used for every water case, but MUWASCO may not be the provider
everywhere in the county. Real routing would pick the water provider by ward. Every water case
goes to one "Water & Sanitation (MUWASCO)" department here, because no authoritative map of
provider service areas was found.

## Privacy (Data Protection Act, 2019)

* **Photos** are decoded and re-encoded from pixels, which strips EXIF (GPS, device serial,
  timestamps). They're stored in the database and served only to the owner and responsible
  officers.
* **Followers** see a case's status and history, but not its description or photo, which might
  contain someone else's details.
* **Open311 reads are public** (the spec intends transparency) but redacted: no description,
  photo or reporter, and coordinates rounded to 3 decimals (~110 m).
* **SMS** carry only the reference, category and status. A phone's lock screen is not private.
* A stranger requesting someone else's case gets a 404, exactly as for a case that doesn't exist,
  so case IDs can't be probed.

## Location without a map

The map isn't usable by everyone (keyboard-only, screen readers, phones without GPS), so a
citizen can choose a ward instead. Those reports are marked "approximate", use the ward's
centre, and are excluded from duplicate matching (they would all match each other). Officers
rely on the landmark text.

## Open311

GeoReport v2 in JSON and XML. Creating a report needs a citizen's personal API key, generated
on their account page and stored hashed, so a report filed by an app still belongs to a real
person. The key is accepted in the POST body (per the spec) or the query string (what Code for
America's client libraries actually send; see `docs/evidence/open311_client_check.txt`).

## SMS outbox

Messages are queued in a table inside the same transaction as the status change and sent after
commit. A rolled-back change never sends a text, and an Africa's Talking outage never blocks
an officer. Failures are retried by `run_case_maintenance`, up to 5 attempts.

## Deployment

Docker image, PostGIS, Render blueprint. The free tier has no cron, so `MAINTENANCE_LOOP=1`
runs the 15-minute maintenance job inside the web container while it's awake. On a paid plan,
use a Render cron job running `python manage.py run_case_maintenance` instead.
