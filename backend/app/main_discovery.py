from .main import *
from fastapi import Query, HTTPException, Depends
from sqlalchemy.orm import Session
from .database import get_db, SessionLocal
from .models import CatalogueItem, RecommendationFeedback, Memory
from .schemas import FeedbackCreate, InternetQuery
from .services.discovery import discover, web_discover
from .seed_profile import SEED_MEMORIES

# Discovery data is separate from the user's personal library. Seed it automatically
# so the first search is useful without requiring a demo-library import.
def _bootstrap_discovery_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Memory).count() == 0:
            for memory in SEED_MEMORIES:
                db.add(Memory(**memory, is_demo=False))
        if db.query(CatalogueItem).count() == 0:
            from .demo import DEMO_CATALOGUE
            verified = {
                "Memento": {"imdb_rating": 8.4, "ott_india": "Prime Video"},
                "The Invisible Guest": {"imdb_rating": 8.0, "ott_india": "Not currently streaming in India"},
                "Coherence": {"imdb_rating": 7.2, "ott_india": "Not currently streaming in India"},
                "Prisoners": {"imdb_rating": 8.2, "ott_india": "Prime Video"},
            }
            for item in DEMO_CATALOGUE:
                values = dict(item)
                values.update(verified.get(values.get("title", ""), {}))
                db.add(CatalogueItem(**values, is_demo=True))
        verified = {
            "Memento": {"imdb_rating": 8.4, "ott_india": "Prime Video"},
            "The Invisible Guest": {"imdb_rating": 8.0, "ott_india": "Not currently streaming in India"},
            "Coherence": {"imdb_rating": 7.2, "ott_india": "Not currently streaming in India"},
            "Prisoners": {"imdb_rating": 8.2, "ott_india": "Prime Video"},
        }
        for title, metadata in verified.items():
            existing = db.query(CatalogueItem).filter_by(title=title).first()
            if existing:
                if not existing.imdb_rating: existing.imdb_rating = metadata["imdb_rating"]
                if not existing.ott_india: existing.ott_india = metadata["ott_india"]
        db.commit()
    finally:
        db.close()

_bootstrap_discovery_data()

@app.get("/discover")
def get_discover(media_type: str|None=None, query: str|None=None, limit: int=Query(24, ge=1, le=50), db: Session=Depends(get_db)):
    rows = discover(db, media_type, limit, query)
    return [{"item": {k:v for k,v in r["item"].__dict__.items() if k != "_sa_instance_state"}, "score": r["score"], "reasons": r["reasons"], "source": r["source"]} for r in rows]

@app.get("/discover/web")
def discover_web_endpoint(query: str=Query(..., min_length=2, max_length=500), limit: int=Query(8, ge=1, le=20)):
    try: return {"query": query, "results": web_discover(query, limit)}
    except Exception as exc: raise HTTPException(502, f"Web research failed: {exc}") from exc

@app.post("/discover/{catalogue_item_id}/feedback")
def feedback(catalogue_item_id: int, payload: FeedbackCreate, db: Session=Depends(get_db)):
    if not db.get(CatalogueItem, catalogue_item_id): raise HTTPException(404, "Discovery candidate not found")
    db.add(RecommendationFeedback(catalogue_item_id=catalogue_item_id, action=payload.action)); db.commit()
    return {"saved": True, "action": payload.action}

@app.get("/catalogue")
def catalogue(media_type: str|None=None, limit: int=Query(100, ge=1, le=500), db: Session=Depends(get_db)):
    q=db.query(CatalogueItem)
    if media_type: q=q.filter(CatalogueItem.media_type == media_type)
    rows=q.order_by(CatalogueItem.created_at.desc()).limit(limit).all()
    return [{k:v for k,v in r.__dict__.items() if k != "_sa_instance_state"} for r in rows]

@app.post("/research/search")
def research_search(payload: InternetQuery):
    try: return {"query": payload.query, "results": web_discover(payload.query, 10)}
    except Exception as exc: raise HTTPException(502, f"Web research failed: {exc}") from exc
