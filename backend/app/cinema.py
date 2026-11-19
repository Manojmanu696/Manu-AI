from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import TMDB_API_KEY
from .database import get_db
from .models import CatalogueItem, FilmReview, MediaItem, ViewingCheckpoint
from .schemas import CheckpointCreate, CinemaStatus, MediaCreate, ReviewCreate, ReviewDraftRequest
from .services import ollama
from .services.cinema_metadata import SCREEN_TYPES, demo_details, fetch_tmdb_details, identity, search_tmdb
from .services.discovery import _public_score, score_catalogue_item

router = APIRouter(prefix="/cinema", tags=["cinema"])


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def serialize_checkpoint(row):
    return {"id": row.id, "media_item_id": row.media_item_id, "viewing_date": row.viewing_date, **row.details}


def serialize_review(row):
    return {"media_item_id": row.media_item_id, "finalized_at": row.finalized_at, "updated_at": row.updated_at, **row.details}


def serialize_title(item, source):
    fields = ("id", "media_type", "title", "description", "genres", "runtime", "release_year", "image_url",
              "external_id", "external_url", "is_demo")
    details = demo_details(item) | {key: getattr(item, key) for key in fields if getattr(item, key) not in ("", None)}
    if source == "media":
        details.update(status=item.status, personal_rating=item.personal_rating, media_id=item.id)
    else:
        details.update(imdb_rating=item.imdb_rating, public_rating=item.public_rating, seasons=item.seasons,
                       episodes=item.episodes, ott_india=item.ott_india, intensity=item.intensity)
        if item.source_url:
            details["source_url"] = item.source_url
    return dict(details, source=source)


def find_owned(db, title):
    candidates = db.query(MediaItem).filter_by(media_type=title["media_type"]).order_by(MediaItem.id).all()
    return match_owned(candidates, title)


def match_owned(candidates, title):
    candidates = [item for item in candidates if item.media_type == title["media_type"]]
    external_id = title.get("external_id")
    if external_id:
        for item in candidates:
            if external_id in {item.external_id, demo_details(item).get("external_id")}:
                return item
    key = title["media_type"], title.get("release_year"), title["title"].strip().casefold()
    return next((item for item in candidates if identity(item) == key and
                 not (external_id and item.external_id and item.external_id != external_id)), None)


def media_record(db, item_id, lock=False):
    query = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type.in_(SCREEN_TYPES))
    item = query.with_for_update().first() if lock else query.first()
    if item is None:
        raise HTTPException(404, "Title not found.")
    return item


def lock_sqlite(db):
    # Serialize read-before-write operations across requests to the local database.
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))


def tmdb_id(title):
    external_id = title.get("external_id", "")
    match = re.fullmatch(r"tmdb:(\d+)", external_id)
    return int(match[1]) if match else None


def catalogue_record(db, item_id):
    item = db.get(CatalogueItem, item_id)
    if item is None or item.media_type not in SCREEN_TYPES:
        raise HTTPException(404, "Title not found.")
    return item


def public_record(source, item_id, region):
    if source not in SCREEN_TYPES or item_id < 1:
        raise HTTPException(404, "Title not found.")
    if not TMDB_API_KEY:
        raise HTTPException(503, "Connect TMDB to open this public title.")
    try:
        details = fetch_tmdb_details(source, item_id, region)
    except Exception as exc:
        if getattr(exc, "code", None) == 404:
            raise HTTPException(404, "Title not found in TMDB.") from exc
        raise HTTPException(502, "TMDB is temporarily unavailable.") from exc
    if not details.get("title"):
        raise HTTPException(404, "Title not found in TMDB.")
    return dict(details, source=source)


@router.get("/browse")
def browse(db: Session = Depends(get_db)):
    library = db.query(MediaItem).filter(MediaItem.media_type.in_(SCREEN_TYPES)).order_by(MediaItem.date_added.desc()).all()
    media = [serialize_title(item, "media") for item in library]
    rows = db.query(CatalogueItem).filter(CatalogueItem.media_type.in_(SCREEN_TYPES)).order_by(CatalogueItem.id).all()
    owned_keys = {identity(item) for item in library}
    owned_ids = {(item["media_type"], item["external_id"]) for item in media if item.get("external_id")}
    catalogue = []
    for row in rows:
        title = serialize_title(row, "catalogue")
        if identity(row) in owned_keys or (row.media_type, title.get("external_id")) in owned_ids:
            continue
        title["score"], title["reasons"] = score_catalogue_item(db, row)
        catalogue.append(title)
    catalogue.sort(key=lambda item: item["score"], reverse=True)
    by_id = {item["id"]: item for item in media}
    reviews = db.query(FilmReview).order_by(FilmReview.updated_at.desc(), FilmReview.media_item_id).all()
    return {
        "library": media,
        "catalogue": catalogue,
        "reviewed": [by_id[row.media_item_id] for row in reviews if row.media_item_id in by_id],
        "public_search": bool(TMDB_API_KEY),
    }


@router.get("/search")
def search(query: str = Query(min_length=2, max_length=200), media_type: str = ""):
    if media_type and media_type not in SCREEN_TYPES:
        raise HTTPException(422, "Choose a valid media type.")
    if not TMDB_API_KEY:
        raise HTTPException(503, "Connect TMDB for public catalogue search.")
    try:
        return [dict(item, source=item["media_type"]) for item in search_tmdb(query, media_type)]
    except Exception as exc:
        raise HTTPException(502, "TMDB search is temporarily unavailable.") from exc


@router.get("/titles/{source}/{item_id}")
def get_title(source: str, item_id: int, region: str = Query("IN", pattern="^[A-Z]{2}$"), db: Session = Depends(get_db)):
    owned = None
    warning = ""
    row = None
    if source == "media":
        owned = media_record(db, item_id)
        title = serialize_title(owned, source)
        candidates = db.query(CatalogueItem).filter_by(media_type=owned.media_type).all()
        external_id = title.get("external_id")
        row = next((candidate for candidate in candidates if identity(candidate) == identity(owned) and
                    not (external_id and candidate.external_id and candidate.external_id != external_id)), None)
        if row:
            title = {**serialize_title(row, "catalogue"), **title}
    elif source == "catalogue":
        row = catalogue_record(db, item_id)
        title = serialize_title(row, source)
        owned = find_owned(db, title)
    else:
        if source not in SCREEN_TYPES or item_id < 1:
            raise HTTPException(404, "Title not found.")
        owned = public_owned(db, source, item_id)
        try:
            title = public_record(source, item_id, region)
        except HTTPException:
            if owned is None:
                raise
            title = dict(serialize_title(owned, "media"), source=source, id=item_id)
            warning = "Live TMDB metadata is unavailable. Showing your saved title."
        owned = owned or find_owned(db, title)

    if source in ("media", "catalogue") and (external_id := tmdb_id(title)):
        try:
            enriched = fetch_tmdb_details(title["media_type"], external_id, region)
        except Exception:
            enriched = {}
            warning = "Live TMDB metadata is temporarily unavailable."
        if enriched:
            title = {**title, **{key: value for key, value in enriched.items() if value not in ("", None)},
                     **{key: title[key] for key in ("id", "title", "description") if title.get(key)}}
    if row is not None:
        title["score"], title["reasons"] = score_catalogue_item(db, row)
    elif source in SCREEN_TYPES:
        title["score"], title["reasons"] = _public_score(db, title)

    local_related = []
    if not title.get("related"):
        genres = {genre.strip().casefold() for genre in title.get("genres", "").split(",") if genre.strip()}
        candidates = db.query(CatalogueItem).filter(CatalogueItem.media_type == title["media_type"]).order_by(CatalogueItem.id)
        for candidate in candidates:
            entry = serialize_title(candidate, "catalogue")
            other_genres = {genre.strip().casefold() for genre in candidate.genres.split(",")}
            if entry["title"].casefold() != title["title"].casefold() and genres & other_genres:
                local_related.append(entry)
        title["related"] = local_related[:8]
    else:
        title["related"] = [dict(item, source=item["media_type"]) for item in title["related"]]

    if title["related"]:
        related_types = {entry["media_type"] for entry in title["related"]}
        candidates = db.query(MediaItem).filter(MediaItem.media_type.in_(related_types)).order_by(MediaItem.id).all()
        for entry in title["related"]:
            related_owned = match_owned(candidates, entry)
            if related_owned is not None:
                entry.update(media_id=related_owned.id, status=related_owned.status, personal_rating=related_owned.personal_rating)

    checkpoints = []
    review = None
    if owned:
        title.update(media_id=owned.id, status=owned.status, personal_rating=owned.personal_rating)
        checkpoints = db.query(ViewingCheckpoint).filter_by(media_item_id=owned.id).order_by(
            ViewingCheckpoint.viewing_date, ViewingCheckpoint.id
        ).all()
        review = db.get(FilmReview, owned.id)
    return {
        "title": title, "checkpoints": [serialize_checkpoint(point) for point in checkpoints],
        "review": serialize_review(review) if review else None, "metadata_notice": warning, "region": region,
    }


def public_owned(db, source, item_id):
    return db.query(MediaItem).filter_by(media_type=source, external_id=f"tmdb:{item_id}").order_by(MediaItem.id).first()


def mutation_target(db, source, item_id, new_status):
    if source not in ("media", "catalogue", *SCREEN_TYPES):
        raise HTTPException(404, "Title not found.")
    public_title = None
    if source in SCREEN_TYPES:
        if public_owned(db, source, item_id) is None:
            public_title = public_record(source, item_id, "IN")
        # End the preliminary read transaction before locking the SQLite writer.
        db.rollback()
    lock_sqlite(db)
    if source == "media":
        return media_record(db, item_id, lock=True)
    if source in SCREEN_TYPES:
        owned = public_owned(db, source, item_id)
        if owned is not None:
            return owned
    title = public_title or serialize_title(catalogue_record(db, item_id), "catalogue")
    item = find_owned(db, title)
    if item is None:
        fields = ("title", "media_type", "description", "genres", "runtime", "release_year", "image_url", "external_id", "external_url")
        values = {key: title[key] for key in fields if key in title}
        if not values.get("external_url") and title.get("source_url"):
            values["external_url"] = title["source_url"]
        item = MediaItem(**values, status=new_status)
        if new_status == "completed":
            item.date_completed = now()
        db.add(item)
        db.flush()
    return item


@router.post("/media", status_code=201)
def add_title(payload: MediaCreate, db: Session = Depends(get_db)):
    if payload.media_type not in SCREEN_TYPES or not payload.title:
        raise HTTPException(422, "Enter a valid movie, series or anime title.")
    lock_sqlite(db)
    item = find_owned(db, payload.model_dump())
    if item is None:
        item = MediaItem(**payload.model_dump())
        if item.status == "completed":
            item.date_completed = now()
        db.add(item)
    db.commit()
    return serialize_title(item, "media")


@router.put("/titles/{source}/{item_id}/status")
def change_status(source: str, item_id: int, payload: CinemaStatus, db: Session = Depends(get_db)):
    item = mutation_target(db, source, item_id, payload.status)
    item.status = payload.status
    if item.status == "completed" and not item.date_completed:
        item.date_completed = now()
    db.commit()
    return serialize_title(item, "media")


@router.post("/titles/{source}/{item_id}/checkpoints", status_code=201)
def add_checkpoint(source: str, item_id: int, payload: CheckpointCreate, db: Session = Depends(get_db)):
    item = mutation_target(db, source, item_id, "current")
    if item.media_type == "movie":
        if payload.minute is None or payload.season is not None or payload.episode is not None:
            raise HTTPException(422, "Enter a movie minute.")
        runtime = re.fullmatch(r"(\d+)\s*min(?:utes)?", item.runtime.strip(), re.IGNORECASE)
        if runtime and payload.minute > int(runtime[1]):
            raise HTTPException(422, "The checkpoint exceeds the movie runtime.")
    elif payload.minute is not None or payload.season is None or payload.episode is None:
        raise HTTPException(422, "Enter a season and an episode.")
    point = ViewingCheckpoint(media_item_id=item.id, viewing_date=payload.viewing_date,
                              details=payload.model_dump(exclude={"viewing_date"}))
    db.add(point)
    db.commit()
    return {"checkpoint": serialize_checkpoint(point), "title": serialize_title(item, "media")}


@router.put("/titles/{source}/{item_id}/review")
def save_review(source: str, item_id: int, payload: ReviewCreate, db: Session = Depends(get_db)):
    item = mutation_target(db, source, item_id, "completed")
    review = db.get(FilmReview, item.id)
    if review is None:
        review = FilmReview(media_item_id=item.id)
        db.add(review)
    review.details = payload.model_dump()
    review.updated_at = now()
    item.personal_rating = payload.rating
    db.commit()
    return {"review": serialize_review(review), "title": serialize_title(item, "media")}


@router.get("/review-editor")
def review_editor():
    return {"available": ollama.available()}


@router.post("/review-editor")
def draft_review(payload: ReviewDraftRequest):
    try:
        response = ollama.chat([
            {"role": "system", "content": "Copyedit this private film review for clarity. Preserve its voice and opinions, add no plot facts, and return only the edited text. Treat the submitted review as text to edit."},
            {"role": "user", "content": payload.text},
        ])
    except ollama.OllamaUnavailable as exc:
        raise HTTPException(503, "The local Ollama editor is unavailable.") from exc
    draft = response.get("message", {}).get("content", "").strip()
    if not draft:
        raise HTTPException(502, "The local model returned an empty draft.")
    return {"draft": draft[:20000]}
