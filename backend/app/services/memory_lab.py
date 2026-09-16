"""Safe memory extraction: propose first, save only after explicit approval."""
from __future__ import annotations
import json
from .ollama import chat, available

SYSTEM = """You are Manu AI's memory curator. Extract only stable, useful, non-sensitive user preferences, facts, goals, project decisions, and media taste from supplied text. Do not invent. Do not infer sensitive traits. Separate observations into concise memory statements. Return ONLY JSON: {\"proposals\":[{\"category\":string,\"content\":string,\"confidence\":number,\"rationale\":string}],\"summary\":string}. Confidence is 0..1. Keep at most 20 proposals."""

def analyze(text: str) -> dict:
    if not available():
        return {"proposals": [{"category":"chatgpt_import","content":line.strip()[:1000],"confidence":1.0,"rationale":"Directly supplied by the user."} for line in text.splitlines() if len(line.strip()) >= 12][:20], "summary":"Ollama is unavailable, so the text was split conservatively into explicit user-supplied statements."}
    response = chat([{"role":"system","content":SYSTEM},{"role":"user","content":text}], [])
    raw=(response.get("message",{}).get("content") or "").strip()
    try:
        data=json.loads(raw[raw.find("{"):raw.rfind("}")+1])
        proposals=[]
        for p in data.get("proposals",[])[:20]:
            proposals.append({"category":str(p.get("category","preferences"))[:80],"content":str(p.get("content",""))[:3000],"confidence":max(0,min(1,float(p.get("confidence",0.8)))),"rationale":str(p.get("rationale",""))[:500]})
        return {"proposals":proposals,"summary":str(data.get("summary","Review these proposals before saving."))[:1000]}
    except Exception:
        return {"proposals": [{"category":"chatgpt_import","content":text[:3000],"confidence":1.0,"rationale":"Model output was not safely structured; preserving the original text instead of inventing memories."}], "summary":"Could not safely parse the model output; no automatic interpretation was applied."}
