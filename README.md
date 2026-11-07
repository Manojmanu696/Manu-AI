# Manu AI

Manu AI is a local-first film, television, and anime discovery app. It builds a live public catalogue automatically, ranks titles against an editable local taste profile, and keeps your library, ratings, feedback, and notes in SQLite on your device.

## Start locally

Requirements: Python 3.11+ and Node.js 20+.

```bash
cp .env.example .env
# Add TMDB_API_KEY to .env (see Provider setup below)
./start.sh
```

Open [http://localhost:3000](http://localhost:3000). The app starts an API at port 8000 and a Next.js frontend at port 3000. The API docs are at [http://localhost:8000/docs](http://localhost:8000/docs). Stop the processes with Ctrl+C.

## Automatic discovery

The home feed does not need library entries to show public titles. On first open it returns immediately, starts provider ingestion in the background, and refreshes the page data as sections arrive. Later opens render the SQLite catalogue first and refresh expired sections in the background. If a provider is unavailable, the last successful section remains visible with a stale-data notice and retry time. Use **Refresh** to request an immediate refresh.

The default India-aware feed includes trending, popular, now playing, upcoming, recent releases, top rated, hidden gems, psychological and mystery collections, short titles, completed short series, and popular/current-season anime. Personalized rows use locally stored library interactions, explicit taste signals, feedback, and public catalogue quality signals. A completed unrated title is neutral.

## Provider setup

### TMDB

TMDB supplies movie/TV catalogues, artwork, release data, ratings, genres, trailers, credits, and India watch-provider listings. Create a free non-commercial API key from your TMDB account settings via the [TMDB getting started guide](https://developer.themoviedb.org/docs/getting-started), then set:

```dotenv
TMDB_API_KEY=your_key_here
```

Restart the backend after changing `.env`. The key is read server-side and is never sent to browser code. Without it, AniList and TVmaze discovery still run and the page gives a setup message.

TMDB requires its approved logo and this notice in the app: “This product uses the TMDB API but is not endorsed or certified by TMDB.” Streaming provider data is supplied through TMDB's partnership with JustWatch; the app credits JustWatch and links to the current TMDB availability page. Do not remove these credits. Review [TMDB attribution requirements](https://developer.themoviedb.org/docs/faq) before publishing. A commercial product requires a separate TMDB license.

### AniList and TVmaze

AniList's public GraphQL API supplies popular anime, current-season anime, and live anime search. It needs no key. Requests retry throttling and transport errors with bounded backoff. See [AniList API documentation](https://docs.anilist.co/guide/rate-limiting).

TVmaze supplies complementary TV catalogue/search data. Its public API needs no key. TVmaze data is attributed in-app and under its [API terms](https://www.tvmaze.com/api/plans); its API responses should be cached for at least 60 minutes.

### Exact environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `TMDB_API_KEY` | Recommended | Movie, TV, and India watch-provider catalogue |
| `DATABASE_URL` | No | Defaults to local SQLite at `data/manu_ai.db` |
| `ALLOWED_ORIGINS` | No | Browser origins allowed by the local API |
| `WEB_REQUEST_TIMEOUT_SECONDS` | No | Public-provider timeout, default 10 seconds |
| `OLLAMA_URL`, `OLLAMA_MODEL` | No | Existing local AI chat integration |
| `OLLAMA_EMBEDDING_MODEL` | No | Local-only sentence similarity model; defaults to `all-minilm` |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | No | Existing optional AI configuration; not used for private recommendation ranking |

Keep real credentials in `.env`; it is ignored by Git. Never put provider keys in `NEXT_PUBLIC_*` variables.

## Refresh and local data

Provider snapshots and section metadata live in `catalogue_items` and `discovery_section_cache`. Trending refreshes every 4 hours, popular every 8 hours, upcoming/top rated/curated discovery every 24 hours, recent releases every 12 hours, and anime trending every 12 hours. Details and India availability refresh when a title page is opened and its details are older than 12 hours. Provider requests have a 10 second timeout, bounded concurrency, three retries, and backoff for rate limits and transient errors.

Schema changes use the ordered additive runner in `backend/app/migrations.py`; existing library and memory rows are retained. Before moving or changing devices, open **Data → Download complete backup**. The ZIP/JSON restore flow remains available from **Data**. The database and backup folder are local; public providers receive only public catalogue/search requests, never the private library or taste memories.

## Recommendation behavior

Candidate retrieval and ranking are separate. The local ranker applies explicit taste signals, rated history, per-title feedback, a cautious public rating/vote-count signal, temporary mood controls, seen-title suppression, and diversity penalties. “Excellent fit” and related labels describe relative ordering, not a probability of enjoyment. A completion is not a like. Feedback can be undone, including the local library side effect created by a completion/watchlist action.

Taste signals record direction, strength, confidence, source, evidence, and confirmation time. Explicit preferences and inferred hypotheses are separate and editable in **Memory**. Alongside structured matching and token overlap, Manu can build sentence embeddings using a local Ollama instance. To enable them, install Ollama, run `ollama pull all-minilm`, and keep `OLLAMA_URL` pointed at loopback. Vectors and source text remain in local SQLite; remote Ollama hosts are rejected. If Ollama is absent, lexical and structured ranking continue without blocking the feed. No taste data is sent to TMDB, AniList, or TVmaze.

## Development and checks

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
cd frontend
npm run lint
npx tsc --noEmit
npm run build
npx playwright install chromium
npm run test:e2e
```

Backend tests use an offline SQLite database and mocked provider responses. Browser tests mock the backend and cover discovery feedback/undo, filtered search, title details, and backup download. Neither suite requires a live API key.

## Architecture and support

See [architecture](docs/ARCHITECTURE.md), [data model](docs/DATA_MODEL.md), [provider details](docs/PROVIDERS.md), and [local setup](docs/LOCAL_SETUP.md). The branch implementation is a single-user local app and does not require Redis, a cloud database, or a vector service.

Common fixes:

- **No movies or shows:** add `TMDB_API_KEY` to `.env`, restart, and choose **Refresh**.
- **Only AniList/TVmaze titles appear:** TMDB has no key or could not be reached; the feed keeps other providers and cached data available.
- **A title has no availability listing:** TMDB has no India provider record for it; Manu does not infer availability from other services.
- **The browser cannot reach the API:** keep `./start.sh` running and confirm `NEXT_PUBLIC_API_URL` points to `http://localhost:8000` if overridden.
- **Port is in use:** stop the process using 3000/8000 or configure the launch script.
