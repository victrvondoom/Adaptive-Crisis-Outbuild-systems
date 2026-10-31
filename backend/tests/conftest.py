"""Shared fixtures for the AIDNEXUS ONE test suite."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.state_engine import CrisisStateEngine


@pytest.fixture
def engine():
    """Fresh deterministic engine (seed=42) per test."""
    return CrisisStateEngine(seed=42)


@pytest.fixture
def client():
    """FastAPI TestClient against a fresh app instance."""
    from fastapi.testclient import TestClient
    from app.main import app
    app.state.__dict__.pop("_tested", None)
    return TestClient(app)
