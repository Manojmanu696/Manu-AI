from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'manu_ai.db'}")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "auto")
WEB_REQUEST_TIMEOUT_SECONDS = int(os.getenv("WEB_REQUEST_TIMEOUT_SECONDS", "10"))
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
