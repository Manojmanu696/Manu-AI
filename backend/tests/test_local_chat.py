import io
import json
import zipfile

from app.services import ollama


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
