# Local setup

1. Install Python 3.11+ and Node.js 20+.
2. In a terminal, enter the project directory and run `chmod +x start.sh` once.
3. Run `./start.sh`.
4. Open `http://localhost:3000`.

The script creates a Python virtual environment, installs backend dependencies, installs frontend packages, starts FastAPI at port 8000, and starts Next.js at port 3000. Stop both with `Ctrl+C`.

For development, run backend tests with:

```bash
.venv/bin/python -m pytest backend/tests
```

Build the frontend with `cd frontend && npm run build`.

