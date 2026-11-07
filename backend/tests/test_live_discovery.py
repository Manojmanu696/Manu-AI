import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database import SessionLocal
from app.migrations import migrate
from app.models import Base, CatalogueItem, MediaItem, RecommendationFeedback, DiscoverySectionCache, TasteSignal, TasteEmbedding, Memory
from app.services import home_feed
from app.services.evaluation import precision_at_k, recall_at_k, ndcg_at_k, catalogue_coverage, intra_list_diversity, novelty_at_k
from app.services.home_feed import score_candidate, rank_catalogue
from app.services.providers import _tmdb_rows, request_json


def test_completion_without_rating_is_neutral():
    db = SessionLocal()
    try:
        candidate = CatalogueItem(media_type="movie", title="A different mystery", genres="Mystery", description="Clever plot")
        watched = MediaItem(media_type="movie", title="A completed mystery", genres="Mystery", status="completed", sentiment="neutral", personal_rating=None)
        db.add_all([candidate, watched]); db.commit(); db.refresh(candidate)
        before = score_candidate(candidate, [], [], [], [])[0]
        after = score_candidate(candidate, [watched], [], [], [])[0]
        assert before == after
        assert watched.status == "completed" and watched.personal_rating is None
    finally:
        db.close()


def test_short_series_mode_requires_completed_series_and_explanations_fit_runtime():
    db = SessionLocal()
    try:
        finished = CatalogueItem(media_type="tv", title="Finished compact series", episodes=12, seasons=1, runtime_minutes=42, series_status="Ended")
        ongoing = CatalogueItem(media_type="tv", title="Ongoing compact series", episodes=12, seasons=1, runtime_minutes=42, series_status="Returning Series")
        long_running = CatalogueItem(media_type="tv", title="Long series", episodes=73, seasons=8, runtime_minutes=60, series_status="Ended")
        db.add_all([finished, ongoing, long_running]); db.commit()
        context = {"history": [], "memories": [], "signals": [], "events": [], "feedback_genres": {},
                   "seen_ids": set(), "seen_titles": set(), "exclude_provider_ids": set(), "semantic_similarities": {}}
        ranked = rank_catalogue(db, [finished, ongoing, long_running], mode="short_series", context=context)
        assert [row["item"].title for row in ranked if row["score"] >= 58] == ["Finished compact series"]

        memory = Memory(category="recommendations", content="Prefer short, engaging, non-filler series.", source="user")
        _, reasons = score_candidate(long_running, [], [memory], [], [])
        assert "compact, engaging" not in " ".join(reasons)
    finally:
        db.close()


def test_feedback_completion_is_neutral_and_undo_restores_library(client):
    # Importing the discovery module attaches its routes to the shared app.
    import app.main_discovery  # noqa: F401

    db = SessionLocal()
    try:
        item = CatalogueItem(media_type="movie", title="Feedback title", external_id="tmdb:movie:991", source_provider="tmdb", provider_id="991")
        db.add(item); db.commit(); item_id = item.id
    finally:
        db.close()
    response = client.post(f"/discover/{item_id}/feedback", json={"action": "completed"})
    assert response.status_code == 200
    feedback_id = response.json()["feedback_id"]
    db = SessionLocal()
    try:
        library_item = db.query(MediaItem).filter_by(external_id="tmdb:movie:991").one()
        assert library_item.status == "completed"
        assert library_item.personal_rating is None
        assert library_item.sentiment == "neutral"
    finally:
        db.close()
    undone = client.post(f"/feedback/{feedback_id}/undo")
    assert undone.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(MediaItem).filter_by(external_id="tmdb:movie:991").count() == 0
        assert db.get(RecommendationFeedback, feedback_id).undone is True
    finally:
        db.close()


def test_tmdb_normalization_preserves_provider_identity_and_attribution():
    rows = _tmdb_rows("movie", [{"id": 42, "title": "The Test", "release_date": "2025-04-02", "overview": "A mystery", "genre_ids": [9648], "poster_path": "/poster.jpg", "vote_average": 7.4, "vote_count": 350, "original_language": "en"}], {9648: "Mystery"}, "trending_movies")
    assert rows[0]["external_id"] == "tmdb:movie:42"
    assert rows[0]["source_provider"] == "tmdb"
    assert rows[0]["source_url"] == "https://www.themoviedb.org/movie/42"
    assert rows[0]["genres"] == "Mystery"
    assert rows[0]["vote_count"] == 350


def test_provider_refresh_does_not_clear_cached_detail_metadata():
    db = SessionLocal()
    try:
        cached = CatalogueItem(media_type="movie", title="A detail title", source_provider="tmdb", provider_id="detail-1",
                               watch_providers_json='[{"name":"Sample Stream","type":"flatrate"}]', countries_json='["IN"]')
        db.add(cached); db.commit()
        refreshed = home_feed._upsert_item(db, {"media_type": "movie", "title": "A detail title", "source_provider": "tmdb",
                                                "provider_id": "detail-1", "external_id": "tmdb:movie:detail-1", "description": "Refreshed"})
        db.commit(); db.refresh(refreshed)
        assert refreshed.watch_providers_json == '[{"name":"Sample Stream","type":"flatrate"}]'
        assert refreshed.countries_json == '["IN"]'
    finally:
        db.close()


def test_request_json_retries_rate_limit(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise HTTPError(request.full_url, 429, "rate limit", {"Retry-After": "0"}, None)
        return BytesIO(b'{"ok":true}')

    monkeypatch.setattr("app.services.providers.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.providers.time.sleep", lambda _: None)
    assert request_json("https://example.test/data") == {"ok": True}
    assert calls["count"] == 2


def test_migration_adds_provider_columns_without_losing_legacy_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE catalogue_items (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"))
        connection.execute(text("CREATE TABLE recommendation_feedback (id INTEGER PRIMARY KEY, catalogue_item_id INTEGER NOT NULL, action VARCHAR(30) NOT NULL)"))
        connection.execute(text("CREATE TABLE discovery_section_cache (section_key VARCHAR(80) PRIMARY KEY, expires_at DATETIME)"))
        connection.execute(text("INSERT INTO catalogue_items(id, title) VALUES (1, 'Saved legacy title')"))
    migrate(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("catalogue_items")}
    with engine.connect() as connection:
        title = connection.execute(text("SELECT title FROM catalogue_items WHERE id=1")).scalar_one()
    assert title == "Saved legacy title"
    assert {"source_provider", "provider_id", "watch_providers_json", "details_fetched_at", "countries_json"} <= columns
    assert 8 in {row[0] for row in engine.connect().execute(text("SELECT version FROM schema_migrations"))}
    engine.dispose()


def test_provider_outage_keeps_cached_section_and_surfaces_error(monkeypatch):
    class FailingTMDB:
        def fetch_sections(self):
            raise RuntimeError("provider unavailable in offline test")

    class EmptyProvider:
        errors = {}
        def fetch_sections(self):
            return {"popular_anime": [], "seasonal_anime": []}

    class EmptyTVMaze:
        errors = {}
        def fetch_sections(self):
            return {"tvmaze_catalogue": []}

    monkeypatch.setitem(home_feed.PROVIDERS, "tmdb", FailingTMDB())
    monkeypatch.setitem(home_feed.PROVIDERS, "anilist", EmptyProvider())
    monkeypatch.setitem(home_feed.PROVIDERS, "tvmaze", EmptyTVMaze())
    db = SessionLocal()
    try:
        item = CatalogueItem(media_type="movie", title="Cached mystery", source_provider="tmdb", provider_id="7001", external_id="tmdb:movie:7001")
        db.add(item); db.flush()
        cache = DiscoverySectionCache(section_key="trending_movies", provider="tmdb", catalogue_ids_json=json.dumps([item.id]),
                                      fetched_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=1),
                                      expires_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(hours=1))
        db.add(cache); db.commit(); item_id = item.id
    finally:
        db.close()
    home_feed._refresh_worker(force=True)
    db = SessionLocal()
    try:
        stored_cache = db.get(DiscoverySectionCache, "trending_movies")
        assert json.loads(stored_cache.catalogue_ids_json) == [item_id]
        assert "provider unavailable" in stored_cache.last_error
        snapshot = home_feed.home_snapshot(db)
        assert snapshot["sections"]["trending_movies"]["items"][0]["item"].title == "Cached mystery"
        assert snapshot["sections"]["trending_movies"]["stale"] is True
    finally:
        db.close()


def test_feedback_undo_removes_temporary_inferred_signal(client):
    import app.main_discovery  # noqa: F401
    db = SessionLocal()
    try:
        item = CatalogueItem(media_type="movie", title="Too slow", source_provider="tmdb", provider_id="7002", external_id="tmdb:movie:7002")
        db.add(item); db.commit(); item_id = item.id
    finally:
        db.close()
    response = client.post(f"/discover/{item_id}/feedback", json={"action": "not_interested", "reason": "too_slow"})
    assert response.status_code == 200
    feedback_id = response.json()["feedback_id"]
    db = SessionLocal()
    try:
        assert db.query(TasteSignal).filter_by(evidence="Feedback on Too slow").count() == 1
    finally:
        db.close()
    assert client.post(f"/feedback/{feedback_id}/undo").status_code == 200
    db = SessionLocal()
    try:
        assert db.query(TasteSignal).filter_by(evidence="Feedback on Too slow").count() == 0
    finally:
        db.close()


def test_offline_ranking_metrics_fixture_is_reproducible():
    fixture = json.loads((Path(__file__).parent / "fixtures" / "recommendation_eval.json").read_text())
    ranked = fixture["ranked_ids"]
    relevant = set(fixture["relevant_ids"])
    genres = {item: set(values) for item, values in fixture["genres"].items()}
    metrics = {"precision@3": precision_at_k(ranked, relevant, 3), "recall@3": recall_at_k(ranked, relevant, 3),
               "ndcg@3": ndcg_at_k(ranked, relevant, 3), "coverage": catalogue_coverage(ranked, fixture["catalogue_size"]),
               "diversity@4": intra_list_diversity(genres, ranked, 4), "novelty@4": novelty_at_k(fixture["popularity"], ranked, 4)}
    assert metrics["precision@3"] == 2 / 3
    assert metrics["recall@3"] == 1.0
    assert 0 < metrics["ndcg@3"] <= 1
    assert metrics["coverage"] == 0.5
    assert metrics["diversity@4"] > 0
    assert metrics["novelty@4"] > 0


def test_local_semantic_embeddings_are_cached_and_private(monkeypatch):
    from app.services import embeddings

    monkeypatch.setattr(embeddings, "OLLAMA_EMBEDDING_MODEL", "offline-test-model")
    monkeypatch.setattr(embeddings, "OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(embeddings, "_FAILURE_UNTIL", 0.0)
    monkeypatch.setattr(embeddings, "_FAILURE_MESSAGE", "")
    requests = []

    def fake_request(url, method="GET", payload=None, **kwargs):
        requests.append((url, payload))
        return {"embeddings": [[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] for _ in payload["input"]]}

    monkeypatch.setattr(embeddings, "request_json", fake_request)
    db = SessionLocal()
    try:
        liked = MediaItem(media_type="movie", title="The clever mystery", genres="Mystery", description="A careful puzzle", personal_rating=9)
        candidate = CatalogueItem(media_type="movie", title="A new mystery", genres="Mystery", description="An intricate puzzle", source_provider="tmdb", provider_id="embed-1")
        db.add_all([liked, candidate]); db.commit(); db.refresh(candidate)
        assert embeddings.prepare_local_embeddings(db) == 2
        assert embeddings.semantic_similarities(db, [candidate], [liked])[candidate.id] > 0.99
        assert embeddings.prepare_local_embeddings(db) == 0
        assert requests and all(url.startswith("http://127.0.0.1:") for url, _ in requests)

        monkeypatch.setattr(embeddings, "OLLAMA_URL", "http://192.0.2.15:11434")
        assert embeddings.prepare_local_embeddings(db) == 0
        assert len(requests) == 1
    finally:
        db.close()


def test_portable_backup_round_trip_preserves_profile_and_feedback():
    from app.services.portability import export_payload, restore_payload

    source = SessionLocal()
    target_engine = create_engine("sqlite://")
    Base.metadata.create_all(target_engine)
    target = sessionmaker(bind=target_engine)()
    try:
        media = MediaItem(media_type="movie", title="Saved title", status="completed", sentiment="neutral")
        memory = Memory(category="favorite genres", content="Mystery", source="user")
        signal = TasteSignal(dimension="story", value="clever mysteries", direction="positive", source="explicit", evidence="User preference")
        catalogue = CatalogueItem(media_type="movie", title="Feedback title", source_provider="tmdb", provider_id="backup-1")
        source.add_all([media, memory, signal, catalogue]); source.flush()
        feedback = RecommendationFeedback(catalogue_item_id=catalogue.id, action="not_interested", reason="too_slow", context="hidden_gems", undone=False)
        source.add(feedback); source.commit()
        payload = export_payload(source)
        restore_payload(target, payload)
        assert target.query(MediaItem).one().title == "Saved title"
        assert target.query(Memory).one().content == "Mystery"
        assert target.query(TasteSignal).one().evidence == "User preference"
        restored_feedback = target.query(RecommendationFeedback).one()
        assert restored_feedback.action == "not_interested"
        assert restored_feedback.reason == "too_slow"
        assert target.query(CatalogueItem).one().provider_id == "backup-1"
    finally:
        source.close(); target.close(); target_engine.dispose()
