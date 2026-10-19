#!/bin/sh
# Lighthouse against the deployed HTTPS site, where best-practices (HTTPS, HSTS, COOP) can be judged.
#   sh scripts/lighthouse_live.sh https://muranga-service-requests.onrender.com
set -eu
URL=${1:?usage: lighthouse_live.sh https://your-app.onrender.com}
mkdir -p docs/evidence/lighthouse-live
docker run --rm -v "$(pwd):/w" -w /w patrickhulce/lhci-client:0.14.0 sh -c "
  lhci collect --config=lighthouserc.json --url=$URL/ --url=$URL/accounts/login/ --url=$URL/accounts/register/ &&
  lhci upload --config=lighthouserc.json --outputDir=docs/evidence/lighthouse-live &&
  lhci assert --config=lighthouserc.json --assertions.categories:best-practices=error"
