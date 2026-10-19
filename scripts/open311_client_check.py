"""
Exercise this API with an off-the-shelf Open311 client: Code for America's `open311` package
(https://github.com/codeforamerica/open311_python, PyPI open311==1.1). It is Python 2 code, so
it runs in a python:2.7 container. Nothing here is specific to our server; if the client can
list services, post a request and read it back, the API speaks GeoReport v2 the way clients expect.

  docker run --rm --network kenyamojaservices_default -v "$PWD/scripts:/s" python:2.7-slim \
      sh -c "pip install -q open311==1.1 && python /s/open311_client_check.py http://web:8000/open311/v2 KEY"
"""
from __future__ import print_function

import json
import sys

from open311 import Open311

endpoint, api_key = sys.argv[1], sys.argv[2]
log = []


def step(name, value):
    log.append((name, value))
    print("%-34s %s" % (name, value))
    sys.stdout.flush()


for fmt in ("xml", "json"):
    client = Open311(endpoint=endpoint, api_key=api_key, format=fmt)
    if fmt == "xml":
        services = client.service_list()
        step("[%s] services listed" % fmt, ", ".join(s["service_code"] for s in services))
    else:
        # Client bug: service_list() always fetches services.xml, then parses it as `format`.
        step("[%s] services listed" % fmt, "skipped (client hardcodes services.xml; see open311/open311.py:46)")

    posted = client.post_service_request(
        service_code="pipe_burst",
        lat="-0.7210", long="37.1526",  # Murang'a town
        address_string="Near Mukuyu market (Open311 client check)",
        description="Burst pipe flooding the road, posted by the Code for America open311 client (%s)." % fmt,
    )
    if fmt == "xml":
        new = posted["service_requests"]["request"]
    else:
        new = posted[0]
    request_id = new["service_request_id"]
    step("[%s] posted, got id" % fmt, "%s (%s)" % (request_id, new.get("service_notice")))

    fetched = client.get_service_request(request_id)
    if fmt == "xml":
        fetched = fetched["service_requests"]["request"]
    else:
        fetched = fetched[0]
    step("[%s] read back" % fmt, "status=%s ward=%s due=%s" % (fetched["status"], fetched["address"], fetched["expected_datetime"]))

    if fmt == "xml":
        listed = client.service_requests(service_code="pipe_burst", status="open")
        if isinstance(listed, dict):
            listed = [listed]
        ids = [r["service_request_id"] for r in listed]
        step("[%s] found in open list" % fmt, request_id in ids)
        assert request_id in ids
    else:
        # Same client bug: service_requests() indexes ['service_requests']['request'] whatever the format.
        step("[%s] found in open list" % fmt, "skipped (client assumes XML shape; see open311/open311.py:62)")

print(json.dumps({"ok": True, "steps": log}))
