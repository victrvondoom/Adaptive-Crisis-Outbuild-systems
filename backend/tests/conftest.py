"""Shared fixtures for the AIDNEXUS ONE test suite (Phase II).

Phase II tests run against a TEMPORARY SQLite database per test session; the
legacy in-memory engine tests use persist=False to avoid touching the DB.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DEV_AUTH_ENABLED", "1")


@pytest.fixture
def engine():
    """Fresh deterministic engine (seed=42) — in-memory only for unit tests."""
    from app.state_engine import CrisisStateEngine
    return CrisisStateEngine(seed=42, org_id="ORG-PACIFIC", persist=False)


@pytest.fixture(scope="session")
def temp_db_url(tmp_path_factory):
    """Session-scoped temporary database (SQLite WAL)."""
    import uuid
    path = tmp_path_factory.mktemp("db") / f"test_{uuid.uuid4().hex[:8]}.db"
    return f"sqlite:///{path}"


@pytest.fixture
def client():
    """Auth-aware API test client against a temporary DB.

    Provides `client.login(email, org)` returning auth headers.
    """
    import uuid
    from fastapi.testclient import TestClient
    from app.db import build_engine, run_migrations, get_engine, get_session_factory
    import app.db as db_mod

    test_url = f"sqlite:///./test_api_{uuid.uuid4().hex[:8]}.db"
    engine_obj = build_engine(test_url)
    run_migrations(engine_obj)
    # Point the module-level factory at the test DB
    db_mod._engine = engine_obj
    db_mod._SessionFactory = db_mod.build_session_factory(engine_obj)

    from app.bootstrap import ensure_bootstrap
    ensure_bootstrap()

    from app import main as main_mod
    main_mod.PRODUCTION_ADAPTER = None
    main_mod._build_engines(persist=True)
    tc = TestClient(main_mod.app)

    class AuthClient:
        def __init__(self, testclient):
            self.tc = testclient
            self.tokens = {}

        def login(self, email: str, org: str = "ORG-PACIFIC") -> dict:
            if (email, org) not in self.tokens:
                r = self.tc.post("/api/v1/auth/dev/token", json={"email": email})
                assert r.status_code == 200, f"login failed for {email}: {r.text}"
                self.tokens[(email, org)] = r.json()["access_token"]
            return {"Authorization": f"Bearer {self.tokens[(email, org)]}", "X-Org-Id": org}

        def get(self, path, **kw):
            return self.tc.get(path, **kw)

        def post(self, path, **kw):
            return self.tc.post(path, **kw)

        def put(self, path, **kw):
            return self.tc.put(path, **kw)

    return AuthClient(tc)
