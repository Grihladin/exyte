# Building Code Parser & RAG Stack

This repository contains everything needed to parse the 2021 International Building Code PDF, normalize the contents (chapters, sections, tables, figures), load the data into a pgvector powered Postgres database, and expose a Retrieval-Augmented Generation (RAG) API that can be paired with the bundled NextChat UI. The core goals are:

- Fully reproducible parsing of the source PDF into structured JSON (`parser/`)
- Embedding and persistence pipelines that populate Postgres (`rag/ingestion`)
- A FastAPI service that serves search/query endpoints and an OpenAI-compatible chat interface (`rag/api`)
- A front-end experience powered by NextChat (`NextChat/` submodule)

## Repository layout

```
parser/               PDF parsing pipeline, models, and utilities
rag/                  RAG ingestion pipeline, database schema, API, and LangGraph workflow
NextChat/             ChatGPT Next Web UI (git submodule) configured to hit the local RAG API
docker-compose.yml    Postgres (with pgvector) + API service definition
2021_International_Building_Code.pdf   Default parsing target
pyproject.toml, uv.lock                Python project definition (Python 3.12)
```

## Prerequisites

- Python 3.12.x (the repo uses [`uv`](https://github.com/astral-sh/uv) but `pip` works too)
- Node.js 18+ (for the NextChat UI)
- Docker (optional but recommended for Postgres/pgvector)
- An OpenAI API key if you want real embeddings and LLM responses (otherwise use deterministic fallbacks)

## 1. Clone and install

```bash
git clone --recurse-submodules <this-repo-url>
cd parsing

# Copy environment template
cp .env.example .env
# Fill in POSTGRES_*, OPENAI_API_KEY, etc.

# Install Python dependencies (uv is fastest)
uv sync
# or: pip install -e .
```

If you previously cloned without `--recurse-submodules`, run `git submodule update --init --recursive` to pull `NextChat/`.

## 2. Start the stack with Docker Compose

The Compose file now orchestrates three services:

- `postgres` – Postgres 16 with pgvector plus the schema migrations under `rag/database`
- `rag-api` – builds from the repo `Dockerfile` and exposes the FastAPI RAG server
- `nextchat` – builds the ChatGPT Next Web UI and proxies requests to the local API using the `NEXTCHAT_*` environment variables

Bring the full stack online with:

```bash
docker compose up --build
# or keep it running in the background
docker compose up -d
```

- Postgres listens on `${POSTGRES_PORT:-55432}`
- FastAPI is available on http://localhost:${API_PORT:-8000}
- NextChat is available on http://localhost:${NEXTCHAT_PORT:-3000}

Compose reads `.env`, so you can pin all of the container ports and UI overrides in one place (defaults shown below). Note that `NEXTCHAT_BASE_URL` should **not** include `/v1` because the UI already appends it when proxying OpenAI-compatible calls.

```bash
# Optional overrides consumed by docker-compose.yml
API_PORT=8000
NEXTCHAT_PORT=3000
NEXTCHAT_BASE_URL=http://rag-api:8000
NEXTCHAT_OPENAI_API_KEY=rag-dev       # placeholder key used only inside the container
NEXTCHAT_ACCESS_CODE=                 # set to gate the UI with a passcode
NEXTCHAT_PROXY_URL=
NEXTCHAT_ENABLE_MCP=false
```

If you only need the database (for local dev without containers), run `docker compose up -d postgres`. Likewise you can start a subset such as `docker compose up -d postgres rag-api` when you prefer to run the UI locally via Node.

## 3. Parse the PDF

Run the helper script from the repo root. It uses the configured defaults (2021 IBC PDF, start page 32, full span of pages) but you can override them with flags.

```bash
# Parse the default range (writes to parser/output/)
uv run python parser/src/scripts/run_parser.py

# Parse 50 pages starting at page 100, skipping table Markdown refresh
uv run python parser/src/scripts/run_parser.py --pages 50 --start-page 100 --skip-table-refresh
```

Outputs of interest:

- `parser/output/parsed_document.json` – normalized chapters/sections/tables/figures
- `parser/output/images/` & `parser/output/tables/` – extracted figures and table crops
- `parser/output/table_regions.json` – table detection metadata

## 4. Ingest into Postgres (with embeddings)

Once `parsed_document.json` exists, run the ingestion/embedding script. It loads the JSON, generates embeddings (unless you skip them), and persists everything via `rag/ingestion.DatabaseWriter`.

```bash
uv run python parser/src/scripts/run_embeddings.py \
    --allow-embed-fallback              # enables deterministic embeddings if OPENAI_API_KEY is blank
# or skip embeddings entirely:
uv run python parser/src/scripts/run_embeddings.py --skip-embeddings
```

You can still invoke the underlying CLI directly (`uv run python -m rag.scripts.ingest_document ...`) if you prefer, but the helper keeps everything runnable from repo root. The ingestion scripts look at the same `.env` file for Postgres/OpenAI configuration.

## 5. Interact with the FastAPI RAG service

When you run `docker compose up`, the API container (`rag-api`) is already listening on http://localhost:${API_PORT:-8000}. You can hit it immediately:

```bash
curl http://localhost:8000/health        # service + DB status
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" \
     -d '{"question": "What does section 101 cover?"}'
```

Key endpoints exposed:

- `POST /query` – RAG workflow answering natural-language questions
- `GET /search` – hybrid semantic/keyword search of ingested sections
- `GET /sections/{section_number}` – retrieve a specific section
- `POST /v1/chat/completions` – OpenAI-compatible endpoint used by NextChat

If you prefer to run the API outside Docker for debugging, Start it manually:

```bash
uv run uvicorn rag.api.server:app --reload --host 0.0.0.0 --port 8000
```

That command reads the same `.env` file, so it will connect to whichever Postgres instance your env vars point at (local or Docker).

## 6. Run the NextChat UI against the local API

If you started everything with Docker Compose, the UI is already running at http://localhost:${NEXTCHAT_PORT:-3000}. Compose injects `BASE_URL=${NEXTCHAT_BASE_URL:-http://rag-api:8000}` (no `/v1` suffix) along with the API key, access code, proxy and MCP flags that you expose via the `NEXTCHAT_*` variables in `.env`, so requests stay inside the Docker network.

For local development outside Docker:

```bash
cd NextChat
# .env.local already exists; to reset it run:
# cp .env.template .env.local

# Key values inside .env.local:
#   OPENAI_API_KEY=sk-local-key      # any non-empty value is fine
#   BASE_URL=http://localhost:8000   # NextChat adds /v1 when proxying
#   (optional) CODE=choose-a-password if you want to gate access

npm install        # or pnpm install / yarn
npm run dev        # launches on http://localhost:3000
```

The repository now ships with `NextChat/.env.local`, which already points the UI to `http://localhost:8000`. Adjust the values (e.g., `CODE` for access control) as needed. In the UI settings choose the custom model `building-code-rag` (exposed via `/v1/models`) and start chatting.

## 7. Useful development commands

```bash
# Run parser unit tests
uv run pytest parser

# Re-run linting/formatting (ruff configured in pyproject.toml)
uv run ruff check parser rag

# Refresh submodules (e.g., after updating NextChat upstream)
git submodule update --remote --merge NextChat
```

## Troubleshooting

- **`OPENAI_API_KEY` not set**: use `--allow-embed-fallback` when ingesting to generate deterministic pseudo-embeddings for local testing.
- **Database connection errors**: verify `docker compose logs postgres` and ensure `.env` matches container credentials. `uv run python -m rag.scripts.test_db_connection` is handy.
- **NextChat cannot connect**: confirm that `BASE_URL` in `.env.local` points to `http://localhost:8000` (no `/v1`) and that the FastAPI server is running.
