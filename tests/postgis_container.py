"""
pytest plugin, loaded before Django settings: if DATABASE_URL isn't set, start a real
PostGIS in Docker with Testcontainers and point Django at it. The tests need the real
thing because the rules under test (ST_Contains, ST_DWithin on geography, the status and
append-only triggers, DISTINCT ON / LATERAL in analytics) are PostgreSQL features.
"""

import atexit
import os

if not os.environ.get("DATABASE_URL"):
    from testcontainers.postgres import PostgresContainer

    _container = PostgresContainer("postgis/postgis:16-3.4", username="test", password="test", dbname="test", driver=None)
    _container.start()
    atexit.register(_container.stop)
    os.environ["DATABASE_URL"] = (
        f"postgis://test:test@{_container.get_container_host_ip()}:{_container.get_exposed_port(5432)}/test"
    )
