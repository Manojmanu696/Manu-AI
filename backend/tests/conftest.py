import os
from pathlib import Path
import sys

os.environ["DATABASE_URL"] = "sqlite:///./data/test_manu_ai.db"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app
from app.services import watch_listings


@pytest.fixture(autouse=True)
def clean_db(monkeypatch):
    monkeypatch.setattr(watch_listings, "title_listings", lambda *args: {})
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

