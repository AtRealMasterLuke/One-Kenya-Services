#!/bin/sh
# External quality checks against the production configuration (DEBUG off), run the same way
# locally and in CI. Results go to docs/evidence/.
#
#   docker compose --profile audit up -d --build web-prod
#   sh scripts/audit.sh
#
# Exits non-zero if any check fails. Lighthouse's best-practices category only warns here:
# over plain HTTP it always fails is-on-https, redirects-http and a COOP console message.
# Check it against the HTTPS deployment with scripts/lighthouse_live.sh.
set -u
NET=kenyamojaservices_default
TARGET=http://web-prod:8000
HERE=$(pwd)
STATUS=0
mkdir -p docs/evidence/zap docs/evidence/lighthouse

echo "== waiting for $TARGET"
until docker compose exec -T web-prod python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" >/dev/null 2>&1; do sleep 2; done

echo "== axe-core (WCAG 2.2 A/AA rules), phone + desktop, every role"
docker run --rm --network $NET -v "$HERE:/w" -w /w mcr.microsoft.com/playwright/python:v1.48.0-jammy \
  sh -c "pip install -q playwright==1.48.0 axe-playwright-python==0.1.7 >/dev/null 2>&1 && python scripts/a11y_check.py $TARGET" || STATUS=1

echo "== Lighthouse, mobile on slow 3G (400 kbps, 400 ms RTT, 4x CPU slowdown)"
SESSION=$(docker compose exec -T web-prod sh -c "python manage.py shell < scripts/make_session.py" 2>/dev/null | sed -n 's/^SESSION=//p')
rm -rf .lighthouseci docs/evidence/lighthouse/*
docker run --rm --network $NET -v "$HERE:/w" -w /w patrickhulce/lhci-client:0.14.0 sh -c "
  lhci collect --config=lighthouserc.json --url=$TARGET/accounts/register/ --url=$TARGET/accounts/login/ &&
  lhci collect --config=lighthouserc.json --additive --url=$TARGET/ --url=$TARGET/requests/new/ --url=$TARGET/requests/ \
      --settings.extraHeaders='{\"Cookie\":\"sessionid=$SESSION\"}' &&
  lhci upload --config=lighthouserc.json &&
  lhci assert --config=lighthouserc.json" || STATUS=1

echo "== OWASP ZAP baseline (passive scan + spider)"
cp zap-rules.tsv docs/evidence/zap/  # ZAP reads its rules from the mounted work directory
docker run --rm --network $NET -v "$HERE/docs/evidence/zap:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t $TARGET/ -c zap-rules.tsv -r zap_baseline.html -J zap_baseline.json -w zap_baseline.md || STATUS=1

exit $STATUS
