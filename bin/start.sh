#!/bin/sh
# Container entrypoint: bring the database up to date, load reference data, serve.
set -e

python manage.py migrate --noinput
python manage.py load_wards

if [ "$SEED_DEMO" = "1" ]; then
    python manage.py seed_demo
    # First replay takes a few minutes; run it beside the web server so the port opens promptly.
    python manage.py replay_311 &
fi

if [ "${MAINTENANCE_LOOP:-0}" = "1" ]; then
    # Hosts without a cron service (e.g. Render's free tier): escalate overdue cases,
    # auto-close confirmed ones and retry failed SMS every 15 minutes.
    (while true; do sleep 900; python manage.py run_case_maintenance || true; done) &
fi

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --access-logfile -
