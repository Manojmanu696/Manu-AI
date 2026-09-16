import io
import json


def movie():
    return {"media_type":"movie","title":"The Signal","genres":"Mystery, Science Fiction","personal_rating":9,"sentiment":"like","status":"completed","runtime":"110 min"}


def test_media_crud(client):
    created = client.post("/media", json=movie())
    assert created.status_code == 201
    item = created.json()
    assert item["title"] == "The Signal"
    assert client.get("/media?media_type=movie").json()[0]["id"] == item["id"]
    changed = movie() | {"title":"The Changed Signal", "personal_rating":10}
    assert client.put(f"/media/{item['id']}", json=changed).json()["personal_rating"] == 10
    assert client.delete(f"/media/{item['id']}").status_code == 204


def test_demo_recommendations_and_chat(client):
    assert client.post("/demo/load").json()["loaded"]
    recommendations = client.get("/recommendations").json()
    assert recommendations and recommendations[0]["score"] <= 99
    chat = client.post("/chat", json={"message":"What should I watch tonight?"}).json()
    assert chat["mode"] == "local"
    assert chat["recommendations"]


def test_portable_export_and_restore(client):
    client.post("/media", json=movie())
    payload = client.get("/data/export/json").json()
    assert payload["format"] == "manu-ai-portable-data"
    replacement = client.post("/data/import?replace=true", files={"file": ("backup.json", io.BytesIO(json.dumps(payload).encode()), "application/json")})
    assert replacement.status_code == 200
    archive = client.post("/data/export/zip")
    assert archive.status_code == 200 and archive.content[:2] == b"PK"
