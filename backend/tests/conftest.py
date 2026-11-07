import os
from pathlib import Path
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///./data/test_manu_ai.db"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db(monkeypatch):
    # Provider refreshes start during FastAPI lifespan. Keep ordinary tests
    # deterministic and offline, and let any previous worker finish before
    # dropping the shared test database.
    from app.services import home_feed

    class OfflineProvider:
        errors = {}

        def fetch_sections(self):
            return {}

    monkeypatch.setitem(home_feed.PROVIDERS, "tmdb", OfflineProvider())
    monkeypatch.setitem(home_feed.PROVIDERS, "anilist", OfflineProvider())
    monkeypatch.setitem(home_feed.PROVIDERS, "tvmaze", OfflineProvider())
    deadline = time.monotonic() + 30
    while home_feed._RUNNING and time.monotonic() < deadline:
        time.sleep(0.01)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    deadline = time.monotonic() + 30
    while home_feed._RUNNING and time.monotonic() < deadline:
        time.sleep(0.01)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

