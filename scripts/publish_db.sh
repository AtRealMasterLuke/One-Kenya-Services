#!/bin/sh
# Copy the local database (wards, categories, demo accounts, replayed reports) to the live
# database used by Vercel. Run from the project folder, with Docker running:
#
#   sh scripts/publish_db.sh "postgresql://user:pass@host/neondb?sslmode=require"
#
# The demo accounts get the DEMO_PASSWORD from your local .env. Running it again replaces
# everything in the live database with your local copy.
set -eu
URL=${1:?usage: sh scripts/publish_db.sh "<Neon connection string>"}

docker compose up -d db
echo "== preparing local database"
docker compose run --rm -e SEED_DEMO=0 web sh -c "
  python manage.py migrate --noinput &&
  python manage.py load_wards &&
  python manage.py seed_demo &&
  python manage.py replay_311"

# Neon's "-pooler" address shares connections between sessions; pg_dump's restore script
# blanks search_path for its session, which would leak to the app. Use the direct address.
URL=$(printf '%s' "$URL" | sed 's/-pooler\./\./')

echo "== copying to the live database"
docker compose exec -T db pg_dump -U kenyamoja --no-owner --no-privileges --clean --if-exists kenyamoja \
  | docker run --rm -i postgres:16 psql "$URL" -q -v ON_ERROR_STOP=1 >/dev/null
echo "== done"
