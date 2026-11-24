from app.models import CatalogueItem
from app.database import SessionLocal
from app import cinema
from app.services import ollama
import json


def test_title_prediction_uses_ollama_without_target_rating(client, monkeypatch):
    arrival = client.post("/media", json={"title": "Arrival", "media_type": "movie", "personal_rating": 9}).json()
    client.post("/media", json={"title": "Contact", "media_type": "movie", "personal_rating": 8})
    client.post("/memories", json={"category": "favorite themes", "content": "I enjoy first-contact stories."})

    def chat(messages, *, schema):
        context = json.loads(messages[-1]["content"])
        assert context["title"]["title"] == "Arrival"
        assert "personal_rating" not in context["title"]
        assert [row["title"] for row in context["other_titles"]] == ["Contact"]
        assert context["preferences"][0]["content"] == "I enjoy first-contact stories."
        assert schema["properties"]["score"]["maximum"] == 10
        return {"_model": "test-model", "message": {"content": json.dumps({
            "score": 8.6, "explanation": "The first-contact premise suits your stated taste.",
            "what_you_might_like": ["The first-contact premise fits your interests.", "The mystery rewards close attention."],
            "what_you_might_dislike": ["There is limited evidence about pacing."],
            "verdict": "Consider", "recommendation": "Pick it when you want a thoughtful science-fiction mystery.",
        })}}

    monkeypatch.setattr(ollama, "chat", chat)
    route = f"/cinema/titles/media/{arrival['id']}"
    prediction = client.post(f"{route}/prediction").json()
    assert prediction["score"] == 8.6 and prediction["provider"] == "ollama"
    assert len(prediction["what_you_might_like"]) == 2
    history = client.get("/data/export/json").json()["local_ai_records"]
    assert next(row["data"]["prediction"] for row in history if row["kind"] == "prediction") == prediction
    assert client.get(route).json()["title"]["personal_rating"] == 9
    monkeypatch.setattr(ollama, "chat", lambda *args, **kwargs: {"message": {"content": '{"score": 12}'}})
    assert client.post(f"{route}/prediction").status_code == 502

    def offline(*args, **kwargs):
        raise ollama.OllamaUnavailable("offline")

    monkeypatch.setattr(ollama, "chat", offline)
    failed = client.post(f"{route}/prediction")
    assert failed.status_code == 503 and "score" not in failed.json()


def test_unfiltered_title_search_returns_openable_series_without_tmdb(client, monkeypatch):
    from app.services import tvmaze

    monkeypatch.setattr(cinema, "TMDB_API_KEY", None)
    show = {"id": 82, "name": "Game of Thrones", "premiered": "2011-04-17", "type": "Scripted"}
    monkeypatch.setattr(tvmaze, "request", lambda path, *args:
                        [{"show": show}] if path == "search/shows" else show)
    result = client.get("/cinema/search", params={"query": "game of thrones"}).json()
    assert [(item["title"], item["media_type"]) for item in result] == [("Game of Thrones", "tv")]
    title = result[0]
    route = f"/cinema/titles/{title['source']}/{title['id']}"
    assert client.get(route).json()["title"]["title"] == "Game of Thrones"
    assert client.put(f"{route}/status", json={"status": "want"}).status_code == 200


def test_catalogue_and_media_titles_share_status_and_journal(client):
    with SessionLocal() as db:
        candidate = CatalogueItem(media_type="movie", title="The Signal", release_year=2021, runtime="100 min")
        db.add(candidate)
        db.commit()
        route = f"/cinema/titles/catalogue/{candidate.id}"

    invalid = client.post(f"{route}/checkpoints", json={"viewing_date": "2026-10-10", "minute": 101})
    assert invalid.status_code == 422
    assert client.get("/media").json() == []

    saved = client.put(f"{route}/status", json={"status": "want"}).json()
    second = client.put(f"{route}/status", json={"status": "current"}).json()
    assert saved["media_id"] == second["media_id"]
    media_id = saved["media_id"]
    media_route = f"/cinema/titles/media/{media_id}"
    for day, minute in [(15, 32), (11, 16)]:
        result = client.post(f"{route}/checkpoints", json={
            "viewing_date": f"2026-10-{day}", "minute": minute, "headline": "A twist", "spoiler": True,
        })
        assert result.status_code == 201

    payload = {"rating": 8.5, "verdict": "Precise", "body": "A complicated puzzle.", "spoiler_notes": "Ending"}
    first = client.put(f"{route}/review", json=payload).json()["review"]
    second = client.put(f"{media_route}/review", json=payload | {"rating": 9, "verdict": "Precisely cut"}).json()["review"]
    assert first["finalized_at"] == second["finalized_at"]
    snapshot = client.get(route).json()
    assert snapshot["title"]["status"] == "current"
    assert snapshot["title"]["personal_rating"] == 9
    assert [point["minute"] for point in snapshot["checkpoints"]] == [16, 32]
    assert snapshot["review"]["verdict"] == "Precisely cut"
    assert client.get("/cinema/browse").json()["reviewed"][0]["id"] == media_id


def test_episode_journal_survives_backup_restore(client):
    unused = client.post("/media", json={"media_type": "movie", "title": "Unused"}).json()
    title = client.post("/cinema/media", json={"media_type": "anime", "title": "Pilot", "status": "on_hold"}).json()
    client.delete(f"/media/{unused['id']}")
    route = f"/cinema/titles/media/{title['id']}"
    assert client.post(f"{route}/checkpoints", json={"viewing_date": "2026-10-10", "minute": 10}).status_code == 422
    assert client.post(f"{route}/checkpoints", json={
        "viewing_date": "2026-10-10", "season": 0, "episode": 2, "notes": "A special",
    }).status_code == 201
    review = {"rating": 8, "verdict": "Warm", "body": "An excellent special."}
    assert client.put(f"{route}/review", json=review).status_code == 200

    export = client.get("/data/export/json")
    replaced = client.post("/data/import?replace=true", files={"file": ("backup.json", export.content, "application/json")})
    assert replaced.status_code == 200
    restored = client.get(route).json()
    assert restored["title"]["status"] == "on_hold"
    assert restored["checkpoints"][0]["season"] == 0
    assert restored["checkpoints"][0]["episode"] == 2
    assert restored["review"]["body"] == review["body"]
    assert client.delete(f"/media/{title['id']}").status_code == 204
    assert client.get("/data/export/json").json()["viewing_checkpoints"] == []


def test_tmdb_availability_is_regional_and_saved_link_has_offline_fallback(client, monkeypatch):
    from app import cinema
    from app.services import cinema_metadata

    def example(path, params):
        assert path == "/movie/430"
        return {
            "id": 430, "title": "Example", "release_date": "2025-10-02", "vote_count": 500, "vote_average": 8.1,
            "credits": {"cast": [{"name": "Example actor", "character": "Lead"}]},
            "videos": {"results": [{"site": "YouTube", "type": "Trailer", "official": True, "key": "ABCD1234xyz"}]},
            "watch/providers": {"results": {"IN": {
                "link": "https://www.themoviedb.org/movie/430/watch?locale=IN",
                "flatrate": [{"provider_name": "Example service", "logo_path": "/provider.png"}],
            }}},
        }

    monkeypatch.setattr(cinema, "TMDB_API_KEY", "test")
    monkeypatch.setattr(cinema_metadata, "TMDB_API_KEY", "test")
    monkeypatch.setattr(cinema_metadata, "_tmdb_get", example)
    cinema_metadata.tmdb_details.cache_clear()
    route = "/cinema/titles/movie/430"
    india = client.get(route).json()["title"]
    assert india["public_rating"] == 8.1 and india["rating_source"] == "TMDB"
    assert india["watch_url"].endswith("locale=IN")
    assert india["providers"] == [{"name": "Example service", "access": "Subscription",
                                    "logo_url": "https://image.tmdb.org/t/p/original/provider.png"}]
    assert client.get(f"{route}?region=US").json()["title"]["providers"] == []
    assert client.put(f"{route}/status", json={"status": "want"}).status_code == 200
    monkeypatch.setattr(cinema, "TMDB_API_KEY", None)
    saved = client.get(route).json()
    assert saved["title"]["status"] == "want"
    assert saved["metadata_notice"]
    assert client.put(f"{route}/status", json={"status": "current"}).status_code == 200
    cinema_metadata.tmdb_details.cache_clear()
