# Murang'a Service Requests

Citizens of Murang'a County report broken streetlights, water leaks, potholes and missed
garbage collection, then follow each report from **Pending → In progress → Resolved → Closed**.
County officers work a queue sorted by charter deadline, and administrators see how the county
is doing against those deadlines, ward by ward.

The brief asked for six features. This version adds none beyond them, and instead tries to do
each one the way a county operation would need it:

| Feature | What "done properly" means here |
|---|---|
| Registration / login | Phone-number accounts (the number the county texts), three roles, lockout after 5 failed sign-ins. **Tests prove no citizen can read another's report** over any URL. |
| Submit a request | Pin on a map, use GPS, or pick a ward (for people who can't use a map). **Auto-routed to a ward** (point-in-polygon with shapely) using IEBC boundaries chosen by measurement. **Duplicates within 100 m are offered before the citizen writes anything**, and officers can merge them. Photos are re-encoded with **GPS EXIF removed**. |
| Status tracking | An **enforced state machine**: the service layer *and* a database trigger reject illegal moves. **Append-only history** (a trigger blocks edits and deletes). The citizen, not the officer, confirms a fix, or reopens it. |
| Admin dashboard | Queue per department, ordered by **deadline from the MUWASCO charter** (in working hours, skipping public holidays). Overdue cases highlighted and **escalated** by SMS. |
| Analytics | Open vs resolved, plus **median time to resolve, deadline breach rate and backlog age**, by ward and category, **reconstructable for any past date** from the history. |
| SMS | Africa's Talking (sandbox), sent from an outbox after commit, retried on failure, with no personal details in the text. |

**Live demo:** https://one-kenya-services.vercel.app · **API:** Open311 GeoReport v2 at `/open311/v2/`

---

## Run it (3 commands)

Needs Docker Desktop.

```bash
git clone <this repository> muranga-service-requests && cd muranga-service-requests
cp .env.example .env
docker compose up --build
```

Open http://localhost:8000. The first start downloads the IEBC ward boundaries (~19 MB) and replays
3,654 real complaints in the background, which takes a few minutes.

**Demo accounts** (on your own copy, the password is `DEMO_PASSWORD` in `.env`, default `Murang-a-demo-2026`; for the live demo, use the password given with the submission):

| Phone | Role |
|---|---|
| 0700 000 001, 0700 000 002 | Citizens |
| 0700 000 010 / 011 / 012 | Officers: Water (MUWASCO) / Roads / Environment |
| 0700 000 099 | County administrator (also the Django admin at `/django-admin/`) |

## How it works

### Case lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending: citizen reports
    Pending --> InProgress: officer starts
    Pending --> Merged: officer merges duplicate (note)
    InProgress --> Resolved: officer resolves (note)
    InProgress --> Merged: officer merges duplicate (note)
    Resolved --> Closed: citizen confirms, or 7 days pass
    Resolved --> InProgress: citizen reopens (note)
    Closed --> [*]
    Merged --> [*]
```

The table in `requests_app/statemachine.py` is the only definition. `services.transition()` enforces it
for the app, and a PostgreSQL trigger generated from the same table enforces it for everything else.

### Data model

```mermaid
erDiagram
    USER ||--o{ SERVICE_REQUEST : reports
    USER }o--o| DEPARTMENT : "officer of"
    DEPARTMENT ||--|{ CATEGORY : handles
    CATEGORY ||--o{ SERVICE_REQUEST : "type of"
    WARD ||--o{ SERVICE_REQUEST : "contains (point-in-polygon)"
    SERVICE_REQUEST ||--o{ CASE_EVENT : "history (append-only)"
    SERVICE_REQUEST ||--o| PHOTO : has
    SERVICE_REQUEST ||--o{ FOLLOWER : "followed by"
    SERVICE_REQUEST ||--o{ NOTIFICATION : "SMS outbox"
    SERVICE_REQUEST |o--o{ SERVICE_REQUEST : "merged into / suspected duplicate of"
    USER ||--o{ API_KEY : "Open311 keys"

    SERVICE_REQUEST {
        float latitude
        float longitude
        string status "enforced by trigger"
        datetime due_at "charter deadline, fixed at creation"
        datetime resolved_at
        int escalation_level
    }
    CATEGORY {
        string code "Open311 service_code"
        int sla_hours
        string sla_basis "clock | working"
        bool sla_is_assumed
    }
    WARD {
        string code "IEBC ward code"
        json boundary "GeoJSON polygon"
    }
```

### Layout

```
accounts/        phone-number users, roles, sign-in
requests_app/    the domain: models, statemachine, services, deadlines, geo, analytics,
                 notifications, photos, access rules, views, management commands
open311/         GeoReport v2 API and API keys
templates/ static/   server-rendered pages, one stylesheet, one small script, vendored Leaflet
data/            raw sources (unchanged), categories + charter targets, replay rules, known points
scripts/         independent checks: verify_analytics, compare_ward_sources, a11y, audit, Open311 client
tests/           pytest suite
docs/            decisions, metrics, boundaries, replay, threat model, ASVS, accessibility, usability, evidence
```

## Data sources

| What | Source | Licence / note |
|---|---|---|
| Ward boundaries | IEBC via HDX ("Kenya Admin Boundaries – Election Polling stations") | Downloaded at setup, not redistributed |
| Constituency boundaries (check only) | IEBC via HDX "Kenya – Subnational Administrative Boundaries" | CC BY-IGO, in `data/boundaries/` |
| Water deadlines | [MUWASCO customer service charter](https://muwasco.co.ke/services.html), copy saved in `data/raw/` | Quoted in `data/categories.json` |
| Other deadlines | **Assumed**: no published county targets found | Marked as assumptions in the UI |
| Complaint data | [NYC 311](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9), 1–7 March 2025 | NYC Open Data, unrestricted |
| Place names (check only) | [GeoNames](https://www.geonames.org/) Kenya extract | CC BY 4.0 |
| Public holidays | `holidays` Python package | MIT |

## Decisions and limitations

The full reasoning is in [`docs/decisions.md`](docs/decisions.md). The main trade-offs:

* **Server-rendered Django, not a SPA**: pages of about 5 KB that work without JavaScript, for 3G and
  cheap phones.
* **Five statuses, not four**: *Merged* is terminal and excluded from the figures, so duplicates are
  never counted twice and their reporters aren't lost.
* **Deadlines never move**: a reopened case keeps its original deadline.

**Known limitations**

* No phone verification at registration, and no password reset (both need SMS one-time codes):
  ASVS gaps 2.5 and 2.7 in [`docs/asvs-l1.md`](docs/asvs-l1.md).
* English only.
* Deadlines for roads, lighting and waste are assumptions until the county publishes targets.
* All water cases go to MUWASCO, whose service area may not cover the whole county.
* Ward boundaries date from 2012, and around 1 in 10 gazetteer places disagree with the 2019
  constituency map. A report near a ward border may land in the neighbouring ward's queue.
* Replay locations are NYC's geography mapped onto Murang'a, so ward breakdowns of replay data are
  illustrative.
* On Vercel's free (Hobby) plan the escalation job runs once a day, not every 15 minutes.

Security: [threat model (STRIDE)](docs/threat-model.md) · [OWASP ASVS L1 check](docs/asvs-l1.md).
Accessibility: [WCAG 2.2 notes](docs/accessibility.md).

## Deploy (Vercel)

Vercel runs the website; the database is a free Postgres from **Neon**, added through Vercel.

1. On [vercel.com](https://vercel.com), sign in with GitHub. Choose **Add New → Project**, import
   this repository, and click **Deploy**. (The first deploy shows an error page until step 3 is done.)
2. In the project, open **Storage → Create Database → Neon (Postgres)**, then connect it to the
   project. Vercel adds `DATABASE_URL` to the project's settings.
3. Under **Settings → Environment Variables**, add `DJANGO_SECRET_KEY` (any long random text) and
   `CRON_SECRET` (any random text).
4. Copy the database's connection string (Storage → your database → **.env.local** tab →
   `DATABASE_URL`), then, on your computer, with Docker running:

   ```bash
   sh scripts/publish_db.sh "paste-the-connection-string-here"
   ```

   That builds the wards, categories, demo accounts and replayed reports locally and copies them to
   Neon. The demo accounts get the `DEMO_PASSWORD` from your local `.env`.
5. **Deployments → Redeploy**. Open the `….vercel.app` address and sign in.

To publish later code changes, push to GitHub (Vercel redeploys by itself). If a change adds
migrations, run `publish_db.sh` again.
