# Manu AI Discovery Engine

Manu AI now separates **candidate discovery** from **personal ranking**.

## Flow

1. `CatalogueItem` stores public discovery candidates. It never stores the user's personal rating or private notes.
2. `MediaItem` stores the user's private library and interaction history.
3. `Memory` stores explicit and inferred taste signals separately.
4. `RecommendationFeedback` records like, not-for-me, watchlist, and watched actions.
5. `services/discovery.py` combines these signals into an explainable ranking score.
6. `/discover/web` and `/research/search` can query the public web when the user explicitly searches.
7. Ollama/Qwen remains the local reasoning layer; web tools receive only public queries/URLs, never the private database context.

## Ranking signals

- Repeatedly liked/completed genres
- Repeatedly liked themes/tags
- Genres associated with dislikes/dropped items
- Explicit memory matches
- Short/engaging/non-filler preference when present in memory
- Recommendation feedback
- A small public-quality signal from catalogue rating

The score is an ordering signal, not a probability or guarantee.

## API

- `GET /discover?media_type=movie&limit=24` — personalized local catalogue
- `GET /discover/web?query=...` — public web discovery
- `POST /discover/{catalogue_item_id}/feedback` — learn from user action
- `GET /catalogue` — inspect candidate catalogue
- `POST /research/search` — direct public web search
- `POST /chat` — Ollama reasoning with read-only web tools when needed

This architecture follows a local-first pattern: local inference and private state stay on the machine while public research is a separate, narrow retrieval boundary. Similar local-first systems commonly separate retrieval, provenance, and local inference for reliability and privacy. citeturn0search4turn0search2
