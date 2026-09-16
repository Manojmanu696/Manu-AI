from app.models import CatalogueItem, MediaItem, Memory
from app.services.discovery import discover
from app.database import SessionLocal


def test_discovery_prefers_matching_personal_taste():
    db = SessionLocal()
    try:
        db.add(MediaItem(media_type="movie", title="Loved Mystery", genres="mystery, thriller", tags="twist, clever", personal_rating=9, sentiment="like", status="completed"))
        db.add(Memory(category="preferred pacing", content="I prefer short, engaging, non-filler thrillers", source="user"))
        db.add(CatalogueItem(media_type="movie", title="Sharp Mystery", genres="mystery, thriller", tags="twist, engaging", runtime="110 min", description="A tense mystery with a clever ending"))
        db.add(CatalogueItem(media_type="movie", title="Slow Romance", genres="romance, drama", tags="emotional", runtime="160 min", description="A long relationship drama"))
        db.commit()
        rows = discover(db, media_type="movie", limit=2)
        assert rows[0]["item"].title == "Sharp Mystery"
        assert rows[0]["score"] > rows[1]["score"]
    finally:
        db.close()
