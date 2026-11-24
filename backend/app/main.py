from contextlib import asynccontextmanager
from datetime import datetime, timezone
import io, json, zipfile
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from .cinema import router as cinema_router
from .local_chat import router as local_chat_router
from .config import ALLOWED_ORIGINS, BACKUP_DIR
from .database import Base, engine, get_db, install_integrity_guards
from .models import MediaItem, Memory
from .schemas import ChatRequest, ChatResponse, MediaCreate, MediaOut, MediaUpdate, MemoryCreate, MemoryOut, MemoryImportRequest, MemoryImportResponse, PersonalSnapshot
from .services.ai import current_provider, retrieve_context
from .services.memory_curator import curate_memory
from .services.personal_intelligence import build_profile
from .services.portability import build_zip, csv_text, db_size, export_payload, restore_payload, serialize_media, serialize_memory
from .services.recommendations import recommendations
from .services.ollama import OllamaUnavailable
from .services.local_ai_records import add_record
from .services.evidence import (change_rating, change_status, lock_writes, normalized, personal_media,
                                personal_memories, same_work, save_memory)

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    install_integrity_guards()
    yield

app = FastAPI(title="Manu AI API", version="0.5.0", description="Local-first personal discovery dashboard API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health(): return {"status":"ok","service":"manu-ai","local_first":True}

@app.get("/media", response_model=list[MediaOut])
def list_media(media_type: str|None=Query(None), status: str|None=Query(None), search: str|None=Query(None), db: Session=Depends(get_db)):
    q=personal_media(db)
    if media_type:q=q.filter(MediaItem.media_type==media_type)
    if status:q=q.filter(MediaItem.status==status)
    if search:q=q.filter(MediaItem.title.ilike(f"%{search.strip()}%"))
    return q.order_by(MediaItem.date_added.desc()).all()

@app.post("/media", response_model=MediaOut, status_code=201)
def create_media(payload: MediaCreate, db: Session=Depends(get_db)):
    lock_writes(db)
    values = payload.model_dump()
    if existing := next((row for row in personal_media(db) if same_work(row, values)), None):
        raise HTTPException(409, {"message": "This title is already in your library.", "media_id": existing.id})
    score, status = values.pop("personal_rating"), values.pop("status")
    item = MediaItem(**values, status="unknown")
    db.add(item)
    change_status(db, item, status, "user")
    if score is not None:
        change_rating(db, item, score, "user")
    db.commit()
    return item

@app.put("/media/{item_id}", response_model=MediaOut)
def update_media(item_id: int, payload: MediaUpdate, db: Session = Depends(get_db)):
    lock_writes(db)
    item = personal_media(db).filter_by(id=item_id).first()
    if item is None:
        raise HTTPException(404, "Media item not found")
    values = payload.model_dump(exclude_unset=True)
    identity = {key: values.get(key, getattr(item, key)) for key in ("title", "media_type", "release_year", "external_id")}
    if any(same_work(row, identity) for row in personal_media(db).filter(MediaItem.id != item.id)):
        raise HTTPException(409, "Another library entry already identifies this work.")
    for key, value in values.items():
        if key not in {"status", "personal_rating"}:
            setattr(item, key, value)
    if "status" in values and values["status"] != item.status:
        change_status(db, item, values["status"], "user")
    if "personal_rating" in values:
        change_rating(db, item, values["personal_rating"], "user", reason=values.get("notes", ""))
    db.commit()
    return item

@app.delete("/media/{item_id}",status_code=204)
def delete_media(item_id:int,db:Session=Depends(get_db)):
    item=personal_media(db).filter_by(id=item_id).first()
    if not item:raise HTTPException(404,"Media item not found")
    db.delete(item);db.commit()

@app.get("/memories",response_model=list[MemoryOut])
def list_memories(db:Session=Depends(get_db)):return personal_memories(db).order_by(Memory.created_at.desc()).all()

@app.post("/memories",response_model=MemoryOut,status_code=201)
def create_memory(payload:MemoryCreate,db:Session=Depends(get_db)):
    lock_writes(db)
    memory = save_memory(db, payload.model_dump())
    db.commit()
    return memory

@app.post("/memories/approve", response_model=list[MemoryOut])
def approve_memories(payload: list[MemoryCreate], db: Session = Depends(get_db)):
    if not 1 <= len(payload) <= 20:
        raise HTTPException(422, "Approve between one and twenty memories at a time.")
    lock_writes(db)
    saved = []
    for value in payload:
        saved.append(save_memory(db, {**value.model_dump(), "source": "approved", "confidence": None}))
        db.flush()
    db.commit()
    return saved


@app.put("/memories/{memory_id}", response_model=MemoryOut)
def revise_memory(memory_id: int, payload: MemoryCreate, db: Session = Depends(get_db)):
    lock_writes(db)
    memory = save_memory(db, payload.model_dump(), replace_id=memory_id)
    db.commit()
    return memory

@app.delete("/memories/{memory_id}",status_code=204)
def delete_memory(memory_id:int,db:Session=Depends(get_db)):
    memory=personal_memories(db).filter_by(id=memory_id).first()
    if not memory:raise HTTPException(404,"Memory not found")
    add_record(db, "memory_revision", {"memory_id": memory.id, "previous": serialize_memory(memory), "current": None})
    db.delete(memory);db.commit()

@app.post("/memories/import",response_model=MemoryImportResponse)
def import_memories(payload:MemoryImportRequest,db:Session=Depends(get_db)):
    text=payload.text.strip();chunks=[]
    for block in text.replace("\r","\n").split("\n"):
        line=" ".join(block.split())
        if len(line)>=12:chunks.append(line[:3000])
    lock_writes(db)
    seen={normalized(row.content) for row in personal_memories(db)};imported=[];categories={"movie":"media_taste","anime":"media_taste","game":"games","book":"books","project":"software_engineering","python":"software_engineering","preference":"preferences","prefer":"preferences","like":"preferences","watchlist":"watchlist"}
    for line in chunks:
        key=normalized(line)
        if key in seen:continue
        seen.add(key);category=next((v for k,v in categories.items() if k in key),"imported_context");m=Memory(category=category,content=line,source="chatgpt_import",confidence=None,is_demo=False);db.add(m);imported.append(m)
    db.commit()
    for m in imported:db.refresh(m)
    return {"imported":imported,"summary":f"Imported {len(imported)} memory signals from the pasted ChatGPT context. Review them in Memory before treating inferred signals as permanent."}

@app.post("/memories/curate")
def curate_memories(payload:dict,db:Session=Depends(get_db)):
    text=str(payload.get("text","")).strip()
    if not text:raise HTTPException(400,"text is required")
    try:
        portable = json.loads(text)
    except ValueError:
        portable = None
    if isinstance(portable, dict) and ("media_items" in portable or "MANU_AI_HANDOFF_VERSION" in portable):
        raise HTTPException(422, "Use the Data page to import a backup. Paste a conversation excerpt to propose memories.")
    result = curate_memory(db, text)
    known = {normalized(row.content) for row in personal_memories(db)}
    result["proposals"] = [proposal for proposal in result.get("proposals", [])
                           if normalized(proposal["content"]) not in known]
    return result

@app.get("/profile")
def personal_profile(db:Session=Depends(get_db)):return build_profile(db)

@app.get("/memories/snapshot",response_model=PersonalSnapshot)
def memory_snapshot(db:Session=Depends(get_db)):
    memories=personal_memories(db).order_by(Memory.created_at.asc()).all();media=personal_media(db).order_by(MediaItem.date_added.asc()).all();explicit=[serialize_memory(m) for m in memories if m.source in ("user","approved","chatgpt_import")];inferred=[serialize_memory(m) for m in memories if m.source=="inferred"];library=[serialize_media(i) for i in media];watch=[x for x in library if x.get("status")=="want"]
    instructions="You are receiving a snapshot from Manu AI. Treat user and approved memories as explicit evidence, imported memories as historical claims, inferred memories as hypotheses, and library entries as raw interaction data. Do not invent preferences. Ask before changing important memories."
    return {"generated_at":datetime.now(timezone.utc),"explicit_memories":explicit,"inferred_memories":inferred,"library":library,"watchlist":watch,"instructions_for_chatgpt":instructions}

@app.post("/demo/load")
def add_demo(db: Session = Depends(get_db)):
    raise HTTPException(409, "Demo data is archived separately from the personal library.")

@app.delete("/demo",status_code=204)
def delete_demo(db:Session=Depends(get_db)):
    raise HTTPException(409, "Demo data is quarantined and included in backups.")

@app.get("/recommendations")
def get_recommendations(media_type:str|None=None,limit:int=Query(12,ge=1,le=50),language:str|None=None,max_minutes:int|None=Query(None,ge=1),db:Session=Depends(get_db)):
    return [{**r,"item":serialize_media(r["item"])} for r in recommendations(db,media_type,limit,language,max_minutes)]

@app.post("/chat",response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    message = payload.message.strip()
    if not message:
        raise HTTPException(400, "message is required")
    user = add_record(db, "assistant_chat", {"role": "user", "content": payload.message})
    reply_to = user.id
    db.commit()
    context = retrieve_context(db, message)
    provider = current_provider(db)
    try:
        response = provider.respond(message, context)
        if response.get("mode") == "ollama":
            response.update(mode="local", provider="ollama")
    except OllamaUnavailable as exc:
        from .services.ai import LocalProvider
        response = LocalProvider(db).respond(message, context)
        response.update(mode="local-fallback", provider="recommendation-engine")
        response["assumptions"] = (response.get("assumptions") or []) + [f"Ollama unavailable: {str(exc)[:180]}"]
    add_record(db, "assistant_chat", {
        "role": "assistant", "content": response["answer"], "reply_to": reply_to, "response": response,
    })
    db.commit()
    return response

@app.get("/data/review")
def data_review(db: Session = Depends(get_db)):
    from .models import LocalAIRecord
    from .services.local_ai_records import serialize_record
    rows = db.query(LocalAIRecord).filter_by(kind="data_review").order_by(LocalAIRecord.created_at.desc())
    return [serialize_record(row) for row in rows if not row.data.get("resolved_at")]


@app.get("/data/summary")
def data_summary(db:Session=Depends(get_db)):
    counts={k:personal_media(db).filter_by(media_type=k).count() for k in ["movie","anime","tv","game","book"]};backups=sorted(BACKUP_DIR.glob("ManuAI_Backup_*.zip"),reverse=True)
    return {"database_bytes":db_size(),"counts":counts,"memories":personal_memories(db).count(),"last_backup":backups[0].name if backups else None,"backup_location":str(BACKUP_DIR)}

@app.get("/data/export/json")
def export_json(db:Session=Depends(get_db)):
    content = json.dumps(export_payload(db), indent=2, ensure_ascii=False)
    return StreamingResponse(iter([content]), media_type="application/json", headers={
        "Content-Disposition": "attachment; filename=ManuAI_Complete_Data.json",
        "Cache-Control": "no-store",
    })

@app.get("/data/export/csv")
def export_csv(dataset:str=Query("media"),db:Session=Depends(get_db)):
    rows=[serialize_media(i) for i in personal_media(db).all()] if dataset=="media" else [serialize_memory(i) for i in personal_memories(db).all()];return StreamingResponse(iter([csv_text(rows)]),media_type="text/csv",headers={"Content-Disposition":f"attachment; filename=ManuAI_{dataset}.csv"})

@app.get("/data/export/zip")
@app.post("/data/export/zip")
def export_zip(db:Session=Depends(get_db)):
    path=build_zip(db);return FileResponse(path,media_type="application/zip",filename=path.name)

@app.post("/data/import")
async def import_backup(file:UploadFile=File(...),replace:bool=Query(False),db:Session=Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    limit = 50 * 1024 * 1024
    raw = await file.read(limit + 1)
    try:
        if len(raw) > limit:
            raise ValueError("Backup exceeds the 50 MB limit.")
        if file.filename and file.filename.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                member = archive.getinfo("manu-ai-data.json")
                if member.file_size > limit:
                    raise ValueError("Uncompressed backup exceeds the 50 MB limit.")
                raw = archive.read(member)
        payload = json.loads(raw)
        lock_writes(db)
        backup = build_zip(db).name if replace else None
        result = restore_payload(db, payload, replace)
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, IntegrityError, zipfile.BadZipFile) as exc:
        db.rollback()
        detail = "Invalid or inconsistent database fields." if isinstance(exc, IntegrityError) else str(exc)
        raise HTTPException(400, f"Import failed: {detail}") from exc
    return {"restored": True, **result, "replace": replace, "backup": backup}

app.include_router(cinema_router)
app.include_router(local_chat_router)
