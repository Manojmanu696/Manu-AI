# Manu AI

Manu AI is a private, local-first dashboard for remembering what you watch, read, and play—and discovering what might fit your taste next. Your library lives in a SQLite file on your Mac, not in a required cloud service.

## Start it (one command)

You need **Python 3.11+** and **Node.js 20+**. In Terminal:

```bash
cd /Users/manoj/CodeX
chmod +x start.sh
./start.sh
```

Then open [http://localhost:3000](http://localhost:3000). The first run downloads the required developer packages. Press `Ctrl+C` in the Terminal window to stop Manu AI. Your data remains intact.

## First use

Choose **Load demo data** to see the dashboard populated with clearly marked examples, or use **Add to library** to start with your own media. You can delete demo data at any time from **Data**.

## Back up and restore

Open **Data** in the app and select **Download complete backup**. This creates a portable ZIP containing JSON, CSV files, and a short readme. Keep it anywhere you like, including a folder synced by Google Drive, iCloud Drive, or Dropbox.

To restore on this or another Mac, open **Data**, choose the backup ZIP (or JSON), then choose whether to merge it with your library or replace it. Replacing is always confirmed first.

## Optional OpenAI configuration

Copy `.env.example` to `.env` and add your key there. Manu AI does not require a key: v1 uses a private local recommendation engine by default. A cloud-provider boundary is prepared for an explicit future opt-in; no key is sent anywhere automatically.

## Troubleshooting

- **The page says it cannot connect:** leave `./start.sh` running and wait a few seconds, then refresh.
- **Port already in use:** stop the other process using port 3000 or 8000, then run `./start.sh` again.
- **Want a fresh local library:** close the app and move `data/manu_ai.db` somewhere safe. Do this only after making a backup.
- **API docs:** while running, visit [http://localhost:8000/docs](http://localhost:8000/docs).

## Project layout

`frontend/` is the Next.js interface; `backend/` is the FastAPI service; `data/` contains the portable local database and generated backups. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the technical map.

