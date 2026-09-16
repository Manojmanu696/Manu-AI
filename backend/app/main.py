from contextlib import asynccontextmanager
from datetime import datetime, timezone
import io, json, zipfile
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from .config import ALLOWED_ORIGINS, BACKUP_DIR
from .database import Base, engine, get_db
from .demo import load_demo
from .models import MediaItem, Memory
from .schemas import ChatRequest, ChatResponse, MediaCreate, MediaOut, MediaUpdate, MemoryCreate, MemoryOut, MemoryImportRequest, MemoryImportResponse, PersonalSnapshot
from .services.ai import current_provider, retrieve_context
from .services.discovery import discover, web_discover
from .services.memory_curator import curate_memory
from .services.personal_intelligence import build_profile
from .services.portability import build_zip, csv_text, db_size, export_payload, restore_payload, serialize_media, serialize_memory
from .services.recommendations import recommendations
from .services.ollama import OllamaUnavailable

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Manu AI API", version="0.5.0", description="Local-first personal discovery dashboard API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health(): return {"status":"ok","service":"manu-ai","local_first":True}

@app.get("/media", response_model=list[MediaOut])
def list_media(media_type: str|None=Query(None), status: str|None=Query(None), search: str|None=Query(None), db: Session=Depends(get_db)):
    q=db.query(MediaItem)
    if media_type:q=q.filter(MediaItem.media_type==media_type)
    if status:q=q.filter(MediaItem.status==status)
    if search:q=q.filter(MediaItem.title.ilike(f"%{search.strip()}%"))
    return q.order_by(MediaItem.date_added.desc()).all()

@app.post("/media", response_model=MediaOut, status_code=201)
def create_media(payload: MediaCreate, db: Session=Depends(get_db)):
    values=payload.model_dump()
    if values["status"]=="completed":values["date_completed"]=datetime.now(timezone.utc).replace(tzinfo=None)
    item=MediaItem(**values);db.add(item);db.commit();db.refresh(item);return item

@app.put("/media/{item_id}", response_model=MediaOut)
def update_media(item_id:int,payload:MediaUpdate,db:Session=Depends(get_db)):
    item=db.get(MediaItem,item_id)
    if not item:raise HTTPException(404,"Media item not found")
    for k,v in payload.model_dump().items():setattr(item,k,v)
    if item.status=="completed" and not item.date_completed:item.date_completed=datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit();db.refresh(item);return item

@app.delete("/media/{item_id}",status_code=204)
def delete_media(item_id:int,db:Session=Depends(get_db)):
    item=db.get(MediaItem,item_id)
    if not item:raise HTTPException(404,"Media item not found")
    db.delete(item);db.commit()

@app.get("/memories",response_model=list[MemoryOut])
def list_memories(db:Session=Depends(get_db)):return db.query(Memory).order_by(Memory.created_at.desc()).all()

@app.post("/memories",response_model=MemoryOut,status_code=201)
def create_memory(payload:MemoryCreate,db:Session=Depends(get_db)):
    memory=Memory(**payload.model_dump());db.add(memory);db.commit();db.refresh(memory);return memory

@app.delete("/memories/{memory_id}",status_code=204)
def delete_memory(memory_id:int,db:Session=Depends(get_db)):
    memory=db.get(Memory,memory_id)
    if not memory:raise HTTPException(404,"Memory not found")
    db.delete(memory);db.commit()

@app.post("/memories/import",response_model=MemoryImportResponse)
def import_memories(payload:MemoryImportRequest,db:Session=Depends(get_db)):
    text=payload.text.strip();chunks=[]
    for block in text.replace("\r","\n").split("\n"):
        line=" ".join(block.split())
        if len(line)>=12:chunks.append(line[:3000])
    seen=set();imported=[];categories={"movie":"media_taste","anime":"media_taste","game":"games","book":"books","project":"software_engineering","python":"software_engineering","preference":"preferences","prefer":"preferences","like":"preferences","watchlist":"watchlist"}
    for line in chunks:
        key=line.lower()
        if key in seen:continue
        seen.add(key);category=next((v for k,v in categories.items() if k in key),"imported_context");m=Memory(category=category,content=line,source="chatgpt_import",confidence=1.0,is_demo=False);db.add(m);imported.append(m)
    db.commit()
    for m in imported:db.refresh(m)
    return {"imported":imported,"summary":f"Imported {len(imported)} memory signals from the pasted ChatGPT context. Review them in Memory before treating inferred signals as permanent."}

@app.post("/memories/curate")
def curate_memories(payload:dict,db:Session=Depends(get_db)):
    text=str(payload.get("text","")).strip()
    if not text:raise HTTPException(400,"text is required")
    return curate_memory(db,text)

@app.get("/profile")
def personal_profile(db:Session=Depends(get_db)):return build_profile(db)

@app.get("/memories/snapshot",response_model=PersonalSnapshot)
def memory_snapshot(db:Session=Depends(get_db)):
    memories=db.query(Memory).order_by(Memory.created_at.asc()).all();media=db.query(MediaItem).order_by(MediaItem.date_added.asc()).all();explicit=[serialize_memory(m) for m in memories if m.source in ("user","chatgpt_import")];inferred=[serialize_memory(m) for m in memories if m.source=="inferred"];library=[serialize_media(i) for i in media];watch=[x for x in library if x.get("status")=="want"]
    instructions="You are receiving a snapshot from Manu AI. Treat explicit/chatgpt_import memories as user-provided context, inferred memories as hypotheses, and library entries as raw interaction data. Do not invent preferences. Ask before changing important memories."
    return {"generated_at":datetime.now(timezone.utc),"explicit_memories":explicit,"inferred_memories":inferred,"library":library,"watchlist":watch,"instructions_for_chatgpt":instructions}

@app.post("/demo/load")
def add_demo(db:Session=Depends(get_db)):return {"loaded":load_demo(db)}

@app.delete("/demo",status_code=204)
def delete_demo(db:Session=Depends(get_db)):
    db.query(MediaItem).filter_by(is_demo=True).delete();db.query(Memory).filter_by(is_demo=True).delete();db.commit()

@app.get("/recommendations")
def get_recommendations(media_type:str|None=None,limit:int=Query(12,ge=1,le=50),db:Session=Depends(get_db)):
    return [{"item":serialize_media(r["item"]),"score":r["score"],"reasons":r["reasons"]} for r in recommendations(db,media_type,limit)]

# Real discovery endpoints used by the Home search. Local library contents are never required.
@app.get("/discover")
def get_discover(media_type:str|None=None,limit:int=Query(18,ge=1,le=50),query:str|None=None,db:Session=Depends(get_db)):
    return discover(db,media_type,limit,query)

@app.post("/research/search")
def research_search(payload:dict):
    query=str(payload.get("query","")).strip()
    if not query:raise HTTPException(400,"query is required")
    try:return {"query":query,"results":web_discover(query,limit=10)}
    except Exception as exc:raise HTTPException(502,f"Web search unavailable: {str(exc)[:220]}") from exc

@app.post("/chat",response_model=ChatResponse)
def chat(payload:ChatRequest,db:Session=Depends(get_db)):
    message=payload.message.strip()
    if not message:raise HTTPException(400,"message is required")
    context=retrieve_context(db,message);provider=current_provider(db)
    try:
        response=provider.respond(message,context)
        if response.get("mode")=="ollama":response["mode"]="local";response["provider"]="ollama"
        return response
    except OllamaUnavailable as exc:
        from .services.ai import LocalProvider
        fallback=LocalProvider(db).respond(message,context);fallback["mode"]="local-fallback";fallback["provider"]="recommendation-engine";fallback["assumptions"]=(fallback.get("assumptions") or [])+[f"Ollama unavailable: {str(exc)[:180]}"];return fallback

@app.get("/data/summary")
def data_summary(db:Session=Depends(get_db)):
    counts={k:db.query(MediaItem).filter_by(media_type=k).count() for k in ["movie","anime","tv","game","book"]};backups=sorted(BACKUP_DIR.glob("ManuAI_Backup_*.zip"),reverse=True)
    return {"database_bytes":db_size(),"counts":counts,"memories":db.query(Memory).count(),"last_backup":backups[0].name if backups else None,"backup_location":str(BACKUP_DIR)}

@app.get("/data/export/json")
def export_json(db:Session=Depends(get_db)):
    content=json.dumps(export_payload(db),indent=2);return StreamingResponse(iter([content]),media_type="application/json",headers={"Content-Disposition":"attachment; filename=ManuAI_Data.json"})

@app.get("/data/export/csv")
def export_csv(dataset:str=Query("media"),db:Session=Depends(get_db)):
    rows=[serialize_media(i) for i in db.query(MediaItem).all()] if dataset=="media" else [serialize_memory(i) for i in db.query(Memory).all()];return StreamingResponse(iter([csv_text(rows)]),media_type="text/csv",headers={"Content-Disposition":f"attachment; filename=ManuAI_{dataset}.csv"})

@app.get("/data/export/zip")
def export_zip(db:Session=Depends(get_db)):
    path=build_zip(db);return FileResponse(path,media_type="application/zip",filename=path.name)

@app.post("/data/import")
async def import_backup(file:UploadFile=File(...),replace:bool=Query(False),db:Session=Depends(get_db)):
    raw=await file.read()
    try:
        if file.filename and file.filename.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:raw=archive.read("manu-ai-data.json")
        payload=json.loads(raw);restore_payload(db,payload,replace)
    except (ValueError,KeyError,json.JSONDecodeError,zipfile.BadZipFile) as exc:raise HTTPException(400,f"Import failed: {exc}") from exc
    return {"restored":True,"media_items":len(payload.get("media_items",[])),"memories":len(payload.get("memories",[])),"replace":replace}
