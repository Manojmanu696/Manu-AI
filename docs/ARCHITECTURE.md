# Architecture

Manu AI is deliberately local-first. The browser interface (Next.js/TypeScript) talks to a small FastAPI service on the same machine. That service validates input with Pydantic, persists data with SQLAlchemy to SQLite, and exposes only JSON and download/upload APIs.

```
Next.js dashboard → FastAPI API → SQLAlchemy → SQLite data/manu_ai.db
                         ├── recommendation service
                         ├── AI provider boundary
                         ├── retrieval/context boundary
                         └── portable import/export service
```

The recommendation service is deterministic and explainable. It scores candidates from ratings, sentiment, completion/drop history, genre/tag overlap, and saved memories. Scores are ordering signals, not probabilities.

The `services/ai.py` `AIProvider` interface isolates cloud and local AI providers. The current `LocalProvider` answers from retrieved local data. Future `OpenAIProvider`, Ollama, Anthropic, and Google providers plug in at this boundary without changing the UI or data model.

`backend/app/agents/` is an intentionally empty boundary for future research, browser, personal-data, calendar, messaging, and shopping agents. Those agents will use services, not bypass the user-owned data model.

External discovery providers should return candidates in the `MediaItem`-compatible form and feed the same recommendation service. No provider is a database dependency.

