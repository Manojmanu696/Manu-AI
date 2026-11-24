from .main import app
from fastapi import Query, HTTPException, Depends
from sqlalchemy.orm import Session
from .database import get_db
from .models import CatalogueItem, RecommendationFeedback
from .schemas import FeedbackCreate, InternetQuery
from .services.discovery import discover, web_discover


def _serialize_item(item):
    if isinstance(item, dict):
        return item
    return {k: v for k, v in item.__dict__.items() if k != "_sa_instance_state"}


@app.get("/discover")
def get_discover(media_type: str|None=None, query: str|None=None, limit: int=Query(24, ge=1, le=50), language: str|None=None, max_minutes: int|None=Query(None, ge=1), db: Session=Depends(get_db)):
    rows = discover(db, media_type, limit, query, language, max_minutes)
    return [{**r, "item": _serialize_item(r["item"])} for r in rows]


@app.get("/discover/web")
def discover_web_endpoint(query: str=Query(..., min_length=2, max_length=500), limit: int=Query(8, ge=1, le=20)):
    try:
        return {"query": query, "results": web_discover(query, limit)}
    except Exception as exc:
        raise HTTPException(502, f"Web research failed: {exc}") from exc


@app.post("/discover/{catalogue_item_id}/feedback")
def feedback(catalogue_item_id: int, payload: FeedbackCreate, db: Session=Depends(get_db)):
    if not db.query(CatalogueItem).filter_by(id=catalogue_item_id, is_demo=False).first(): raise HTTPException(404, "Discovery candidate not found")
    db.add(RecommendationFeedback(catalogue_item_id=catalogue_item_id, action=payload.action)); db.commit()
    return {"saved": True, "action": payload.action}


@app.get("/catalogue")
def catalogue(media_type: str|None=None, limit: int=Query(100, ge=1, le=500), db: Session=Depends(get_db)):
    q=db.query(CatalogueItem).filter_by(is_demo=False)
    if media_type: q=q.filter(CatalogueItem.media_type == media_type)
    rows=q.order_by(CatalogueItem.created_at.desc()).limit(limit).all()
    return [_serialize_item(r) for r in rows]


@app.post("/research/search")
def research_search(payload: InternetQuery):
    try:
        return {"query": payload.query, "results": web_discover(payload.query, 10)}
    except Exception as exc:
        raise HTTPException(502, f"Web research failed: {exc}") from exc
