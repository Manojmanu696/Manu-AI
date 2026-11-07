from datetime import timedelta
import json
from .main import *
from fastapi import Query, HTTPException, Depends
from sqlalchemy.orm import Session
from .database import get_db, SessionLocal
from .models import CatalogueItem, RecommendationFeedback, Memory, MediaItem, TasteSignal
from .schemas import FeedbackCreate, InternetQuery, TasteSignalCreate, TasteSignalOut
from .services.discovery import discover, web_discover
from .services.home_feed import home_snapshot, request_refresh, PROVIDERS, rank_catalogue


def _serialize_item(item):
    if isinstance(item, dict):
        return item
    return {k: v for k, v in item.__dict__.items() if k != "_sa_instance_state"}


@app.get("/discover")
def get_discover(media_type: str|None=None, query: str|None=None, limit: int=Query(24, ge=1, le=50), db: Session=Depends(get_db)):
    rows = discover(db, media_type, limit, query)
    response = []
    for result in rows:
        item = result["item"]
        if isinstance(item, dict) and item.get("source_provider") and item.get("provider_id"):
            from .services.home_feed import _upsert_item
            item = _upsert_item(db, item)
        response.append({"item": _serialize_item(item), "score": result["score"], "fit": result.get("fit"), "reasons": result["reasons"], "source": result["source"]})
    db.commit()
    return response


@app.get("/discover/web")
def discover_web_endpoint(query: str=Query(..., min_length=2, max_length=500), limit: int=Query(8, ge=1, le=20)):
    try:
        return {"query": query, "results": web_discover(query, limit)}
    except Exception as exc:
        raise HTTPException(502, f"Web research failed: {exc}") from exc


@app.post("/discover/{catalogue_item_id}/feedback")
def feedback(catalogue_item_id: int, payload: FeedbackCreate, db: Session=Depends(get_db)):
    item = db.get(CatalogueItem, catalogue_item_id)
    if not item: raise HTTPException(404, "Discovery candidate not found")
    if payload.action == "rate" and payload.rating is None: raise HTTPException(422, "A rating from 1 to 10 is required")
    event = RecommendationFeedback(catalogue_item_id=catalogue_item_id, action=payload.action, reason=payload.reason, context=payload.context, rating=payload.rating)
    db.add(event)
    status = {"watchlist": "want", "started": "current", "completed": "completed", "already_watched": "completed", "dropped": "dropped"}.get(payload.action)
    if status or payload.action == "rate":
        existing = db.query(MediaItem).filter_by(external_id=item.external_id).first() if item.external_id else None
        if not existing:
            event.library_item_created = True
            existing = MediaItem(media_type=item.media_type, title=item.title, description=item.description, genres=item.genres,
                                 tags=item.tags, runtime=item.runtime, release_year=item.release_year, external_id=item.external_id,
                                 external_url=item.external_url, image_url=item.image_url, status=status or "completed",
                                 personal_rating=payload.rating if payload.action == "rate" else None, sentiment="neutral")
            if (status or "completed") == "completed":
                existing.date_completed = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(existing)
        else:
            event.previous_library_state_json = json.dumps({"status": existing.status, "personal_rating": existing.personal_rating,
                                                             "date_completed": existing.date_completed.isoformat() if existing.date_completed else None})
            if status: existing.status = status
            if payload.action == "rate": existing.personal_rating = payload.rating
            if status == "completed" and not existing.date_completed:
                existing.date_completed = datetime.now(timezone.utc).replace(tzinfo=None)
        event.library_item_id = existing.id
        if event.library_item_created:
            db.flush()
            event.library_item_id = existing.id
    if payload.action == "not_interested" and payload.reason:
        dimension_value = {"too_slow": ("pacing", "slow pacing"), "too_emotional": ("emotional_intensity", "high emotional intensity"),
                           "predictable": ("twists", "predictable plot"), "poor_writing": ("writing", "poor writing")}.get(payload.reason)
        if dimension_value:
            signal = TasteSignal(dimension=dimension_value[0], value=dimension_value[1], direction="negative", strength=0.45,
                                 confidence=0.45, source="inferred", evidence=f"Feedback on {item.title}")
            db.add(signal); db.flush(); event.taste_signal_id = signal.id
    db.commit()
    db.refresh(event)
    return {"saved": True, "action": payload.action, "feedback_id": event.id}


@app.get("/home")
def get_home(mode: str=Query("best_fit", pattern="^(best_fit|psychological|mystery|fast_hook|hidden_gems|short_movies|short_series|critically_acclaimed|explore|surprise)$"),
             mood: str=Query("", max_length=80), db: Session=Depends(get_db)):
    return home_snapshot(db, mode=mode, mood=mood)


@app.post("/home/refresh")
def refresh_home(db: Session=Depends(get_db)):
    snapshot = home_snapshot(db, force_refresh=True)
    return {"accepted": True, "refreshing": snapshot["refreshing"], "last_updated": snapshot["last_updated"]}


@app.get("/providers/health")
def provider_health():
    from .services.embeddings import embedding_status
    db = SessionLocal()
    try:
        return {**{name: provider.health() for name, provider in PROVIDERS.items()}, "local_embeddings": embedding_status(db)}
    finally:
        db.close()


@app.get("/taste-signals", response_model=list[TasteSignalOut])
def list_taste_signals(db: Session=Depends(get_db)):
    return db.query(TasteSignal).order_by(TasteSignal.created_at.desc()).all()


@app.post("/taste-signals", response_model=TasteSignalOut, status_code=201)
def create_taste_signal(payload: TasteSignalCreate, db: Session=Depends(get_db)):
    signal = TasteSignal(**payload.model_dump(), confirmed_at=datetime.now(timezone.utc).replace(tzinfo=None) if payload.source == "explicit" else None)
    db.add(signal); db.commit(); db.refresh(signal); return signal


@app.put("/taste-signals/{signal_id}", response_model=TasteSignalOut)
def update_taste_signal(signal_id: int, payload: TasteSignalCreate, db: Session=Depends(get_db)):
    signal = db.get(TasteSignal, signal_id)
    if not signal: raise HTTPException(404, "Preference signal not found")
    for key, value in payload.model_dump().items(): setattr(signal, key, value)
    signal.confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None) if payload.source == "explicit" else None
    db.commit(); db.refresh(signal); return signal


@app.delete("/taste-signals/{signal_id}", status_code=204)
def delete_taste_signal(signal_id: int, db: Session=Depends(get_db)):
    signal = db.get(TasteSignal, signal_id)
    if not signal: raise HTTPException(404, "Preference signal not found")
    db.delete(signal); db.commit()


@app.post("/feedback/{feedback_id}/undo")
def undo_feedback(feedback_id: int, db: Session=Depends(get_db)):
    event = db.get(RecommendationFeedback, feedback_id)
    if not event: raise HTTPException(404, "Feedback not found")
    if event.taste_signal_id:
        signal = db.get(TasteSignal, event.taste_signal_id)
        if signal:
            db.delete(signal)
    if event.library_item_created and event.library_item_id:
        linked = db.get(MediaItem, event.library_item_id)
        if linked:
            db.delete(linked)
    elif event.library_item_id:
        linked = db.get(MediaItem, event.library_item_id)
        if linked:
            state = json.loads(event.previous_library_state_json or "{}")
            linked.status = state.get("status", linked.status)
            linked.personal_rating = state.get("personal_rating", linked.personal_rating)
            linked.date_completed = datetime.fromisoformat(state["date_completed"]) if state.get("date_completed") else None
    event.undone = True
    db.commit()
    return {"undone": True}


@app.get("/catalogue")
def catalogue(media_type: str|None=None, limit: int=Query(100, ge=1, le=500), db: Session=Depends(get_db)):
    q=db.query(CatalogueItem)
    if media_type: q=q.filter(CatalogueItem.media_type == media_type)
    rows=q.order_by(CatalogueItem.created_at.desc()).limit(limit).all()
    return [_serialize_item(r) for r in rows]


@app.get("/catalogue/{catalogue_item_id}")
def catalogue_detail(catalogue_item_id: int, db: Session=Depends(get_db)):
    item = db.get(CatalogueItem, catalogue_item_id)
    if not item: raise HTTPException(404, "Catalogue title not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    details_stale = not item.details_fetched_at or item.details_fetched_at < now - timedelta(hours=12)
    detail_error = ""
    similar_results = []
    if item.source_provider in {"tmdb", "tvmaze"} and details_stale:
        try:
            payload = PROVIDERS[item.source_provider].details(_serialize_item(item))
            similar_rows = payload.pop("similar_items", None)
            for key, value in payload.items():
                if key in CatalogueItem.__table__.columns and key not in {"id", "created_at", "is_demo"}:
                    if key == "source_retrieved_at" and isinstance(value, str):
                        value = now
                    setattr(item, key, value)
            if similar_rows is not None:
                from .services.home_feed import _upsert_item
                similar_items = [_upsert_item(db, row) for row in similar_rows]
                item.similar_catalogue_ids_json = json.dumps([similar.id for similar in similar_items])
                similar_results = similar_items
            item.details_fetched_at = now
            db.commit(); db.refresh(item)
        except Exception as exc:
            # A cached overview remains useful while optional detail providers fail.
            item_error = str(exc)[:240]
            db.rollback()
            item = db.get(CatalogueItem, catalogue_item_id)
            detail_error = item_error
    if not similar_results:
        try:
            similar_ids = json.loads(item.similar_catalogue_ids_json or "[]")
            similar_results = db.query(CatalogueItem).filter(CatalogueItem.id.in_(similar_ids)).all() if similar_ids else []
        except (ValueError, TypeError):
            similar_results = []
    from .services.home_feed import score_candidate, recommendation_caveats, _fit_label
    history = db.query(MediaItem).all()
    memories = db.query(Memory).all()
    signals = db.query(TasteSignal).all()
    events = db.query(RecommendationFeedback).filter_by(undone=False).all()
    from .services.embeddings import semantic_similarities
    fit_score, reasons = score_candidate(item, history, memories, signals, events,
                                         semantic_similarity=semantic_similarities(db, [item], history).get(item.id, 0.0))
    personal = db.query(MediaItem).filter_by(external_id=item.external_id).first() if item.external_id else None
    similar_output = []
    for similar in similar_results:
        similar_score, similar_reasons = score_candidate(similar, history, memories, signals, events)
        similar_output.append({"item": _serialize_item(similar), "fit": _fit_label(similar_score), "reasons": similar_reasons})
    return {**_serialize_item(item), "detail_error": detail_error, "similar_titles": similar_output,
            "recommendation": {"label": _fit_label(fit_score), "reasons": reasons, "caveats": recommendation_caveats(item, history, signals)},
            "personal": {"status": personal.status, "rating": personal.personal_rating, "notes": personal.notes} if personal else None}


@app.post("/research/search")
def research_search(payload: InternetQuery):
    try:
        return {"query": payload.query, "results": web_discover(payload.query, 10)}
    except Exception as exc:
        raise HTTPException(502, f"Web research failed: {exc}") from exc
