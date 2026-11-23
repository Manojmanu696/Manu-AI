# Manu AI

Manu’s Cut is the film, TV and anime home for Manu AI. Browse recommendations, track your watchlist, and keep a private viewing journal and final reviews in the existing local SQLite library. Games, books, web search, memory, and the assistant are available under **Manu AI tools**.

## Start it (one command)

You need **Python 3.11+** and **Node.js 20+**. In Terminal:

```bash
cd Manu-AI
chmod +x start.sh
./start.sh
```

Then open [http://localhost:3000](http://localhost:3000). The first run downloads the required developer packages. Press `Ctrl+C` in the Terminal window to stop Manu AI. Your data remains intact.

## First use

Use **Discover** to search the local catalogue, **My Library → Add a title** to enter your own, or **Load sample library** on an empty home to try the journal with sample records. To remove sample library records, use `DELETE /demo` in the local API docs.

Set `TMDB_API_KEY` in `.env` for public title search and live catalogue details, including regional streaming data. If a local Ollama model is running, the review editor can suggest a draft that you can revise before finalizing. See the [desktop and mobile comparison](docs/manus-cut/README.md).

## Back up and restore

Use **Local chat** on any page to discuss your taste with Ollama. Messages and replies are saved in SQLite. Edit a suggested preference and choose **Remember this** to make it part of the profile used for future predictions. This personalizes the context sent to Ollama each time. It does not fine-tune model weights.

Use **Download my data** in the chat or **Download full backup** in Data to export the library, ratings, memories, journal, conversation history, approved chat preferences, and AI predictions generated after this feature was added. The ZIP includes `local-ai-history.json` and the combined `manu-ai-data.json`. Keep the backup private if it contains personal chats.

Open the local API docs and use `GET /data/export/zip` to download a portable backup. It includes the library, memories, checkpoints, and final reviews in JSON and CSV.

To restore, upload the ZIP or JSON to `POST /data/import` in the local API docs. Leave `replace` off to keep existing records, or set it to `true` to replace the current library with the backup.

## Optional OpenAI configuration

Copy `.env.example` to `.env` and add your key there. Manu AI does not require a key: v1 uses a private local recommendation engine by default. A cloud-provider boundary is prepared for an explicit future opt-in; no key is sent anywhere automatically.

## Troubleshooting

- **The page says it cannot connect:** leave `./start.sh` running and wait a few seconds, then refresh.
- **Port already in use:** stop the other process using port 3000 or 8000, then run `./start.sh` again.
- **Want a fresh local library:** close the app and move `data/manu_ai.db` somewhere safe. Do this only after making a backup.
- **API docs:** while running, visit [http://localhost:8000/docs](http://localhost:8000/docs).

## Project layout

`frontend/` is the Next.js interface; `backend/` is the FastAPI service; `data/` contains the portable local database and generated backups. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the technical map.

