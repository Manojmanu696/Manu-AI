"""Local Ollama client used as Manu AI's private reasoning layer."""
from __future__ import annotations
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from ..config import OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_URL

class OllamaUnavailable(RuntimeError):
    pass

def _request(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(f"{OLLAMA_URL}{path}", data=data, headers={"Content-Type":"application/json"}, method="POST" if payload else "GET")
    try:
        with urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode())
    except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
        raise OllamaUnavailable(str(exc)) from exc

def models() -> list[str]:
    try:
        return [m.get("name", "") for m in _request("/api/tags").get("models", []) if m.get("name")]
    except OllamaUnavailable:
        return []

def model_name() -> str | None:
    if OLLAMA_MODEL.strip():
        return OLLAMA_MODEL.strip()
    available = models()
    for prefix in ("qwen", "llama", "mistral", "gemma", "phi"):
        for name in available:
            if name.lower().startswith(prefix):
                return name
    return available[0] if available else None

def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    model = model_name()
    if not model:
        raise OllamaUnavailable("No local Ollama model is installed")
    payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.2}}
    if tools:
        payload["tools"] = tools
    response = _request("/api/chat", payload)
    response["_model"] = model
    return response

def available() -> bool:
    return bool(models())
