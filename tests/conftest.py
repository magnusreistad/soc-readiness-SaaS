"""
Test isolation: no test may reach Supabase, Postgres or OpenAI.

1. load_dotenv() is neutralised before any app module is imported, so a
   developer's real .env is never read during a test run.
2. Dummy values are forced for every credential the app reads (several
   modules construct clients at import time and need *something* set).
3. Outbound Python sockets are blocked for the whole session, and the
   psycopg2 pool (which connects in C, bypassing the socket guard) is
   replaced with one that raises.
"""

import os
import socket

import dotenv
import pytest

dotenv.load_dotenv = lambda *args, **kwargs: False

_DUMMY_ENV = {
    "OPENAI_API_KEY": "sk-test-dummy",
    "SUPABASE_URL": "https://supabase.invalid",
    "SUPABASE_ANON_KEY": "dummy-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy-service-role-key",
    "SUPABASE_JWT_SECRET": "dummy-jwt-secret",
    "SUPABASE_DB_URL": "postgresql://ci:ci@db.invalid:5432/ci",
    "GITHUB_PAT": "",
    "DEMO_MODE": "false",
    "DEMO_ORG_ID": "0",
    "SLACK_WEBHOOK_URL": "",
    "SMTP_USER": "",
    "SMTP_PASSWORD": "",
}
os.environ.update(_DUMMY_ENV)


class NetworkAccessError(RuntimeError):
    pass


def _blocked_connect(self, address, *args, **kwargs):
    raise NetworkAccessError(f"Tests must not open network connections (attempted {address!r})")


@pytest.fixture(autouse=True, scope="session")
def _no_network():
    original = socket.socket.connect
    socket.socket.connect = _blocked_connect
    try:
        yield
    finally:
        socket.socket.connect = original


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    from app.utils import db_postgres

    def _refuse():
        raise NetworkAccessError("Tests must not connect to Postgres")

    monkeypatch.setattr(db_postgres, "_get_pool", _refuse)
