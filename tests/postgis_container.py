"""
pytest plugin, loaded before Django settings: if DATABASE_URL isn't set, start a real
PostgreSQL in Docker with Testcontainers and point Django at it. The tests need the real
thing because the rules under test (the status and append-only triggers, LATERAL joins in
analytics) are PostgreSQL features.
"""

import atexit
import os

if not os.environ.get("DATABASE_URL"):
    from testcontainers.postgres import PostgresContainer

    _container = PostgresContainer("postgres:16", username="test", password="test", dbname="test", driver=None)
    _container.start()
    atexit.register(_container.stop)
    os.environ["DATABASE_URL"] = (
        f"postgres://test:test@{_container.get_container_host_ip()}:{_container.get_exposed_port(5432)}/test"
    )
