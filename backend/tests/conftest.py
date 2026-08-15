"""Shared pytest fixtures. Data dir is redirected to a temp dir BEFORE app import."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="editonce-test-"))
os.environ["EDITONCE_DATA_DIR"] = str(_TEST_DATA_DIR)
# Deterministic: tests must not depend on a dev machine's real secrets.
os.environ.pop("EDITONCE_GROQ_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)

import pytest  # noqa: E402


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return _TEST_DATA_DIR