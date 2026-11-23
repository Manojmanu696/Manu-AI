import io
import json
import zipfile

from app.database import SessionLocal
from app.models import CatalogueItem, RecommendationFeedback, ResearchSource
from app.services import ollama
from app.services.local_ai_records import add_record
from app.services.rating_feedback import extract_rating_feedback


def test_chat_memory_and_portable_history(client, monkeypatch):
    calls = []

    def respond(messages, *, schema):
        calls.append(messages)
        return {"_model": "test-model", "message": {"content": json.dumps({
            "answer": "That helps distinguish slow pacing from lack of payoff.",
            "suggested_preference": "I enjoy a slow build when it pays off.",
        })}}

    monkeypatch.setattr(ollama, "chat", respond)
    reply = client.post("/local-chat", json={"message": "I suit slow films if they pay off."}).json()
    record_id = reply["assistant"]["id"]
    assert len(client.get("/local-chat").json()) == 2
    assert not client.get("/memories").json()
    saved = "I enjoy a slow build when the payoff is meaningful."
    for _ in range(2):
        response = client.post(f"/local-chat/{record_id}/remember", json={"content": saved})
        assert response.json()["data"]["saved_preference"] == saved
    assert [row["content"] for row in client.get("/memories").json()] == [saved]
    client.post("/local-chat", json={"message": "What did I tell you?"})
    assert saved in calls[1][0]["content"]
    assert any(row["content"] == "I suit slow films if they pay off." for row in calls[1][1:])

    archive = client.get("/data/export/zip")
    with zipfile.ZipFile(io.BytesIO(archive.content)) as exported:
        records = json.loads(exported.read("local-ai-history.json"))
        assert len(records) == 5
        assert any(row["kind"] == "preference" and row["data"]["content"] == saved for row in records)
    restored = client.post("/data/import?replace=true", files={"file": ("local.zip", archive.content)})
    assert restored.status_code == 200
    assert len(client.get("/local-chat").json()) == 4


def test_offline_chat_preserves_user_message(client, monkeypatch):
    def offline(*args, **kwargs):
        raise ollama.OllamaUnavailable("offline")

    monkeypatch.setattr(ollama, "chat", offline)
    response = client.post("/local-chat", json={"message": "I prefer shorter movies."}).json()
    assert response["assistant"] is None and response["error"]
    assert client.get("/local-chat").json()[0]["data"]["content"] == "I prefer shorter movies."


def test_saved_score_calibrates_current_and_similar_title_predictions(client, monkeypatch):
    legacy = ("I think your game of thrones score is less for me. "
              "I would read it around 9.4, so can you update your score and your memory")
    title = {"title": "Game of Thrones", "media_type": "tv", "genres": "Fantasy, Drama", "release_year": 2011}
    with SessionLocal() as db:
        candidate = CatalogueItem(**title)
        db.add(candidate)
        add_record(db, "chat", {"role": "user", "content": legacy, "title": title})
        db.commit()
        catalogue_id = candidate.id
    route = f"/cinema/titles/catalogue/{catalogue_id}"
    assert client.get(route).json()["rating_feedback"]["score"] == 9.4
    assert client.get("/local-chat").json()[0]["data"]["rating_feedback"]["score"] == 9.4
    assert extract_rating_feedback("Would I rate it 9.4?", title) is None
    assert extract_rating_feedback("I would rate it 9.4 or 8.9.", title) is None
    assert extract_rating_feedback("I would rate it 9.44.", title) is None

    def offline(*args, **kwargs):
        raise ollama.OllamaUnavailable("offline")

    monkeypatch.setattr(ollama, "chat", offline)
    response = client.post("/local-chat", json={
        "message": "I'd give Game of Thrones a 9.5/10.", "title_source": "catalogue", "title_id": catalogue_id,
    }).json()
    assert response["user"]["data"]["rating_feedback"]["score"] == 9.5
    assert "9.5/10 feedback for Game of Thrones" in response["assistant"]["data"]["content"]
    saved = client.put(f"{route}/status", json={"status": "want"}).json()
    media_route = f"/cinema/titles/media/{saved['media_id']}"
    assert client.get(media_route).json()["rating_feedback"]["score"] == 9.5
    assert client.get(media_route).json()["title"]["personal_rating"] is None

    prompts = []

    def predict(messages, *, schema):
        prompts.append(json.loads(messages[-1]["content"]))
        return {"_model": "test-model", "message": {"content": json.dumps({
            "score": 9.3, "explanation": "Your feedback shows you enjoy this style of fantasy.",
            "what_you_might_like": ["The political intrigue drives the story.", "The ensemble gives the story depth."],
            "what_you_might_dislike": ["The pace varies between storylines."],
            "verdict": "Worth prioritizing", "recommendation": "Choose it when you want a complex fantasy drama.",
        })}}

    monkeypatch.setattr(ollama, "chat", predict)
    result = client.post(f"{media_route}/prediction").json()
    assert result["score"] == 9.3 and result["rating_feedback"]["score"] == 9.5
    assert prompts[0]["title_rating_feedback"]["score"] == 9.5
    related = client.post("/media", json={"title": "Another fantasy", "media_type": "tv", "genres": "Fantasy"}).json()
    assert client.post(f"/cinema/titles/media/{related['id']}/prediction").status_code == 200
    assert prompts[1]["title_rating_feedback"] is None
    assert prompts[1]["other_rating_feedback"] == [{**title, "score": 9.5}]


def test_complete_chat_download_includes_older_messages_and_reference_data(client, monkeypatch):
    from app.services.ai import LocalProvider

    monkeypatch.setattr("app.main.current_provider", LocalProvider)
    with SessionLocal() as db:
        candidate = CatalogueItem(media_type="movie", title="Export example")
        db.add(candidate)
        db.flush()
        db.add(RecommendationFeedback(catalogue_item_id=candidate.id, action="like"))
        db.add(ResearchSource(catalogue_item_id=candidate.id, url="https://example.com/title"))
        for index in range(105):
            add_record(db, "chat", {"role": "user", "content": f"Full message {index}"})
        db.commit()
    assert client.post("/chat", json={"message": "Message from the AI page"}).status_code == 200
    assert len(client.get("/local-chat").json()) == 100
    archive = client.get("/data/export/json")
    assert archive.headers["content-disposition"] == "attachment; filename=ManuAI_Complete_Data.json"
    payload = archive.json()
    records = payload["local_ai_records"]
    assert len(records) == 107
    assert records[0]["data"]["content"] == "Full message 0"
    assert records[-2]["data"]["content"] == "Message from the AI page"
    assert records[-1]["data"]["reply_to"] == records[-2]["id"]
    assert payload["catalogue_items"][0]["title"] == "Export example"
    assert payload["recommendation_feedback"][0]["action"] == "like"
    assert payload["research_sources"][0]["url"] == "https://example.com/title"


def test_feedback_stays_with_active_title(client, monkeypatch):
    from app.services import tvmaze

    previous = {"title": "Game of Thrones", "media_type": "tv", "release_year": 2011}
    active = {"title": "Chainsaw Man", "media_type": "anime", "release_year": 2022, "id": 63451, "source": "tvmaze"}
    monkeypatch.setattr(tvmaze, "series_details", lambda _: active.copy())
    with SessionLocal() as db:
        db.add(CatalogueItem(**previous))
        old = add_record(db, "chat", {"role": "user", "content": "I would rate it 9.4.", "title": previous})
        add_record(db, "chat", {"role": "assistant", "content": "Discussion of the Iron Throne.", "reply_to": old.id})
        add_record(db, "chat", {"role": "user", "content": "This is just a 6.5 movie for me",
                                "title": active, "rating_feedback": None})
        db.commit()

    assert client.get("/cinema/titles/tvmaze/63451").json()["rating_feedback"]["score"] == 6.5
    reply = client.post("/local-chat", json={
        "message": "This is just a 6.6 movie for me", "title_source": "tvmaze", "title_id": 63451,
    }).json()
    assert reply["assistant"]["data"]["content"] == "Saved your 6.6/10 feedback for Chainsaw Man."
    changed = client.post("/local-chat/feedback/tvmaze/63451", json={"score": 6.5})
    assert changed.json()["score"] == 6.5
    assert client.get("/cinema/titles/catalogue/1").json()["rating_feedback"]["score"] == 9.4
    assert client.post("/local-chat/feedback/tvmaze/63451", json={"score": 11}).status_code == 422

    def respond(messages, *, schema):
        assert '"title": "Chainsaw Man"' in messages[0]["content"]
        assert all("Iron Throne" not in message["content"] for message in messages[1:])
        assert all("I would rate it 9.4." != message["content"] for message in messages[1:])
        return {"_model": "test", "message": {"content": '{"answer":"Discussing Chainsaw Man.", "suggested_preference":null}'}}

    monkeypatch.setattr(ollama, "chat", respond)
    reply = client.post("/local-chat", json={
        "message": "What do you think of this?", "title_source": "tvmaze", "title_id": 63451,
    }).json()
    assert reply["assistant"]["data"]["title"]["title"] == "Chainsaw Man"
