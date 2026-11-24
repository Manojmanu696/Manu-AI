from app.database import SessionLocal
from app.models import MediaItem, Memory
from app.services.evidence import change_status
from app.services.local_ai_records import add_record
from app.services.rating_feedback import extract_rating_feedback, latest_feedback
from app.services.recommendations import score_title, taste


def test_unknown_completion_date_stays_unknown_after_export_and_repeat_update(client):
    with SessionLocal() as db:
        row = MediaItem(title="Confirmed classic", media_type="tv", release_year=2009, status="unknown", sentiment="like")
        db.add(row)
        change_status(db, row, "completed", "user_confirmation", completion_date_known=False)
        db.commit()
        title_id = row.id
    assert client.put(f"/cinema/titles/media/{title_id}/status", json={"status": "completed"}).status_code == 200
    [item] = client.get("/media").json()
    assert (item["status"], item["date_completed"], item["personal_rating"]) == ("completed", None, None)
    assert client.get("/recommendations").json() == []


def test_personal_rating_endpoint_does_not_read_prediction(client):
    created = client.post("/media", json={"title": "Example", "media_type": "movie", "status": "unknown"}).json()
    route = f"/cinema/titles/media/{created['id']}"
    assert client.put(f"{route}/rating", json={"score": 7.2}).json()["personal_rating"] == 7.2
    assert client.put(f"{route}/rating", json={"score": None}).json()["personal_rating"] is None
    result = client.get(route).json()
    assert result["title"]["status"] == "unknown"
    assert [row["score"] for row in result["rating_history"]] == [None, 7.2]


def test_withdrawn_chat_preserved_but_not_used_as_rating(client):
    title = {"title": "Example", "release_year": 2022, "media_type": "anime"}
    assert extract_rating_feedback("I'd rate it around 7.5", title)["precision"] == "approximate"
    with SessionLocal() as db:
        add_record(db, "chat", {"role": "user", "content": "This is just a 6.5 movie for me", "title": title,
                                "rating_feedback_withdrawn": {"reason": "The number belongs to a model prediction."}})
        db.commit()
        assert not latest_feedback(db)
    archive = client.get("/data/export/json").json()
    assert len(archive["rating_feedback_history"]) == 0
    assert archive["local_ai_records"][0]["data"]["content"].endswith("for me")


def test_narrative_signals_filler_and_mixed_reaction():
    with SessionLocal() as db:
        db.add_all([
            Memory(category="story", content="Curiosity, meaningful stakes, progression and payoff.", source="approved"),
            MediaItem(title="Mixed reaction", media_type="movie", personal_rating=6.6,
                      notes="Concept alone is insufficient.", status="unknown"),
            MediaItem(title="Superhero favourite", media_type="movie", genres="action", sentiment="like", status="completed"),
        ])
        db.commit()
        profile = taste(db)
        candidate = {"title": "Example", "genres": "action", "tags": "", "description": "A team plans a rescue mission and must survive."}
        high, reasons = score_title(candidate, profile)
        slow, _ = score_title({**candidate, "tags": "slow start"}, profile)
        filler, _ = score_title({**candidate, "tags": "filler, repetitive"}, profile)
        concept, caveats = score_title({**candidate, "description": "A mysterious secret."}, profile)
        assert high == slow and high > filler and high > concept
        assert any("Superhero favourite" in reason for reason in reasons)
        assert any("Mixed reaction" in caveat for caveat in caveats)
        assert high < 90


def test_seen_recommendations_rotate_without_personal_history_mutation(client, monkeypatch):
    from app.models import CatalogueItem
    from app.services.ai import LocalProvider

    monkeypatch.setattr("app.main.current_provider", LocalProvider)
    with SessionLocal() as db:
        db.add_all([
            CatalogueItem(media_type="movie", title=f"Film {index}", release_year=2020 + index,
                          description="An investigation leads to a dangerous rescue mission.")
            for index in range(6)
        ])
        db.commit()
    first = client.post("/chat", json={"message": "Recommend 3 movies"}).json()["recommendations"]
    second = client.post("/chat", json={"message": "Recommend 3 movies"}).json()["recommendations"]
    assert len(first) == len(second) == 3
    assert {row["title"] for row in first}.isdisjoint(row["title"] for row in second)
    assert client.get("/media").json() == []
