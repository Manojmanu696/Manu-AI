import json

from app.database import SessionLocal
from app.models import CatalogueItem, MediaItem, Memory, RecommendationFeedback, ResearchSource
from app.services.ai import retrieve_context
from app.services.discovery import discover
from app.services.title_prediction import prediction_prompt


def test_feedback_and_viewing_state_are_independent(client):
    created = client.post("/media", json={"title": "Example", "release_year": 2020, "media_type": "movie", "status": "unknown"}).json()
    private_id = created["id"]
    route = f"/cinema/titles/media/{private_id}"
    assert client.get("/recommendations").json() == []
    assert client.put(f"/media/{private_id}", json={"personal_rating": 8.2}).json()["date_completed"] is None
    assert client.put(f"/media/{private_id}", json={"personal_rating": 8.6, "notes": "Strong payoff."}).json()["status"] == "unknown"
    assert client.put(f"{route}/status", json={"status": "want"}).json()["status"] == "want"
    assert client.get("/recommendations").json()[0]["item"]["status"] == "want"
    assert client.get("/media").json()[0]["date_completed"] is None
    assert client.put(f"{route}/status", json={"status": "completed"}).status_code == 200
    assert client.get("/media").json()[0]["date_completed"]
    assert client.get("/recommendations").json() == []
    ratings = [row["data"] for row in client.get("/data/export/json").json()["local_ai_records"] if row["kind"] == "rating_revision"]
    assert [rating["score"] for rating in ratings] == [8.2, 8.6]
    assert ratings[-1]["previous"] == 8.2 and ratings[-1]["source"] == "user" and ratings[-1]["scale"] == 10


def test_rating_only_review_does_not_complete_new_title(client):
    with SessionLocal() as db:
        db.add(CatalogueItem(id=1, title="Review only", media_type="movie"))
        db.commit()
    response = client.put("/cinema/titles/catalogue/1/review", json={"rating": 8, "verdict": "Solid", "body": "Good stakes."})
    assert response.status_code == 200
    [item] = client.get("/media").json()
    assert (item["status"], item["date_completed"], item["personal_rating"]) == ("unknown", None, 8)


def test_demo_negatives_duplicates_and_profile_evidence(client):
    with SessionLocal() as db:
        db.add_all([
            MediaItem(title="Same title", media_type="tv", release_year=2020, status="completed", personal_rating=10, is_demo=True),
            CatalogueItem(id=1, title="Same title", media_type="tv", release_year=2020, description="Mystery and survival"),
            CatalogueItem(id=2, title="Sample only", media_type="tv", is_demo=True),
            CatalogueItem(id=3, title="Dropped", media_type="tv", release_year=2020),
            CatalogueItem(id=4, title="Rejected", media_type="tv", release_year=2020),
            MediaItem(title="Dropped", media_type="tv", release_year=2020, status="dropped"),
            Memory(category="genre", content="Demo-only history", is_demo=True),
        ])
        db.flush()
        db.add(RecommendationFeedback(catalogue_item_id=4, action="not_for_me"))
        db.commit()
    approved = {"category": "story", "content": "I prefer mysteries and meaningful stakes."}
    for _ in range(2):
        assert client.post("/memories/approve", json=[approved]).status_code == 200
    with SessionLocal() as db:
        assert [row["item"].title for row in discover(db)] == ["Same title"]
        assert [memory.source for memory in retrieve_context(db, "mystery")["memories"]] == ["approved"]
        prompt = prediction_prompt(db, {"title": "Other", "media_type": "tv"})
        assert "meaningful stakes" in prompt[-1]["content"] and "Demo-only history" not in prompt[-1]["content"]
    duplicate = {"title": "Same title", "media_type": "tv", "release_year": 2020, "external_id": "tvmaze:tv:200"}
    assert client.post("/media", json=duplicate).status_code == 201
    assert client.post("/media", json={**duplicate, "external_id": "tvmaze:200"}).status_code == 409
    assert client.post("/media", json={**duplicate, "external_id": "tvmaze:201", "release_year": 2022}).status_code == 201
    assert len(client.get("/memories").json()) == 1


def test_restore_preserves_user_edits_and_restores_source_tables(client):
    item = client.post("/media", json={"title": "One", "media_type": "movie", "release_year": 2020, "personal_rating": 8}).json()
    with SessionLocal() as db:
        db.add(CatalogueItem(id=1, title="Research title", media_type="movie", release_year=2012))
        db.flush()
        db.add(RecommendationFeedback(catalogue_item_id=1, action="completed"))
        db.add(ResearchSource(catalogue_item_id=1, url="https://example.com/"))
        db.commit()
    archive = client.get("/data/export/json").json()
    client.put(f"/media/{item['id']}", json={"personal_rating": 9})
    for _ in range(2):
        reply = client.post("/data/import", files={"file": ("data.json", json.dumps(archive))})
        assert reply.json()["conflicts"] == 1 and reply.json()["media_added"] == 0
    assert len(client.get("/media").json()) == 1
    assert client.get("/media").json()[0]["personal_rating"] == 9
    assert len(client.get("/data/review").json()) == 1
    bad = {**archive, "viewing_checkpoints": [{"media_item_id": 123}]}
    assert client.post("/data/import?replace=true", files={"file": ("bad.json", json.dumps(bad))}).status_code == 400
    assert client.get("/media").json()[0]["personal_rating"] == 9
    assert client.post("/data/import?replace=true", files={"file": ("data.json", json.dumps(archive))}).status_code == 200
    restored = client.get("/data/export/json").json()
    assert len(restored["recommendation_feedback"]) == len(restored["research_sources"]) == 1
    assert restored["recommendation_feedback"][0]["action"] == "completed"
    assert restored["media_items"][0]["personal_rating"] == 8


def test_import_preserves_original_scale_and_keeps_demo_quarantined(client):
    payload = {"format": "manu-ai-portable-data", "media_items": [
        {"id": 1, "title": "Old book score", "release_year": 2019, "media_type": "book", "personal_rating": 4,
         "rating_scale": 4, "rating_precision": "historical", "date_added": "2022-01-01T00:00:00Z"},
        {"id": 2, "title": "Old book score", "release_year": 2019, "media_type": "book", "personal_rating": 9,
         "is_demo": True, "status": "completed"},
    ]}
    for _ in range(2):
        assert client.post("/data/import", files={"file": ("data.json", json.dumps(payload))}).status_code == 200
    [item] = client.get("/media").json()
    assert item["personal_rating"] is None and item["status"] == "unknown"
    archive = client.get("/data/export/json").json()
    [rating] = [row["data"] for row in archive["local_ai_records"] if row["kind"] == "rating_revision"]
    assert (rating["score"], rating["scale"], rating["precision"]) == (4, 4, "historical")
    assert len(archive["media_items"]) == 2


def test_audio_and_total_runtime_require_evidence():
    from app.services.recommendations import meets_constraints

    title = {"title": "Show", "media_type": "tv", "audio_languages": ["en"], "episodes": 12, "episode_duration": "24 min"}
    assert meets_constraints(title, "English", 288)
    assert not meets_constraints(title, "English", 287)
    assert not meets_constraints(title, "Japanese", 300)
    assert not meets_constraints({"title": "Unknown", "media_type": "movie"}, "English", 300)


def test_curated_shortlist_excludes_confirmed_dropped_titles(client):
    assert any(row["title"] == "Severance" for row in client.get("/cinema/rankings").json()["Series"])
    assert client.post("/media", json={"title": "Severance", "media_type": "tv", "status": "dropped",
                                      "release_year": 2022}).status_code == 201
    assert "Severance" not in {row["title"] for row in client.get("/cinema/rankings").json()["Series"]}
