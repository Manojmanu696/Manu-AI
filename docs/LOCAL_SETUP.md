# Local setup

1. Install Python 3.11+ and Node.js 20+.
2. Copy `.env.example` to `.env` and add `TMDB_API_KEY` (recommended for movies/TV; anime and TVmaze do not need keys).
3. In a terminal, enter the project directory and run `./start.sh`.
4. Open `http://localhost:3000`; first-open discovery runs automatically in the background.

The script creates a Python virtual environment, installs backend dependencies, installs frontend packages, starts FastAPI at port 8000, and starts Next.js at port 3000. Stop both with `Ctrl+C`. Provider keys stay in the backend `.env` file and are never bundled into browser code.

For development, run backend tests with:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
```

Check the frontend with `cd frontend && npm run lint && npx tsc --noEmit && npm run build`.

The default database is `data/manu_ai.db`. Create a ZIP or JSON backup from **Data** before manual database maintenance or migration. Upgrades run automatically and are additive; do not delete the database to fix a provider error.

