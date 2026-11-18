# KnowledgePilot AI

A local document intelligence app for indexing files, searching workspace knowledge and inspecting the passages behind an answer. The default workflow requires Python dependencies but no API key, cloud account, model download or GPU.

## Start with Docker Desktop

Extract the ZIP and open a terminal in the `knowledgepilot` folder. Start Docker Desktop or a Docker Engine with the Compose plugin, then run:

```sh
docker compose up --build
```

On Windows PowerShell, the equivalent launcher is `powershell -ExecutionPolicy Bypass -File .\start.ps1`. On Linux or macOS, run `sh ./start.sh`. Open [KnowledgePilot](http://localhost:8000), or [OpenAPI docs](http://localhost:8000/docs). The health endpoint is [localhost:8000/health](http://localhost:8000/health). Compose binds to loopback and keeps the database in a named volume. The first build needs network access to pull the Python image and dependencies.

## Start with Python 3.12

Linux or macOS:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

The server initializes SQLite under `data/` on first launch. Set `KP_DB` to choose another writable path.

## Demo

1. Create a local account with a password of at least 10 characters and choose **Load samples**.
2. Ask “How many vacation days do employees receive?” Open the citation to inspect the exact source chunk.
3. Search for “incident escalation” using keyword, TF-IDF cosine, and hybrid modes.
4. Compare `hr-policy.md` with `engineering-runbook.md` using “employees must complete onboarding.”
5. Ask “Where are Martian mineral deposits?” to see an insufficient-evidence response.
6. To test workspace roles, register a second account and use **Manage access** from the first account to grant viewer access to its workspace.

Upload a PDF with selectable text, DOCX, UTF-8 TXT, Markdown, CSV, or HTML. The upload limit is 2 MB per file. Sample documents are fictional and were created for this repository.

## Verify

Use the same Python 3.12 environment for these commands:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/evaluate.py
node --check static/app.js
python scripts/smoke.py --url http://127.0.0.1:8000
```

To run the optional browser check, install `requirements-browser.txt`, run `python -m playwright install chromium`, start the app, then run `python scripts/browser_smoke.py`.

- [Architecture and tradeoffs](docs/architecture.md)
- [API guide](docs/api.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Skill evidence](docs/skill-evidence.md)
- [Verification report](docs/verification.md)
