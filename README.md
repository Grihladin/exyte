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

## 3. Parse the PDF

Run the helper script from the repo root. It uses the configured defaults (2021 IBC PDF, start page 32, full span of pages) but you can override them with flags.

```bash
# Parse the default range (writes to parser/output/)
uv run python parser/src/scripts/run_parser.py
```

Outputs of interest:

- `parser/output/parsed_document.json` – normalized chapters/sections/tables/figures
- `parser/output/images/` & `parser/output/tables/` – extracted figures and table crops
- `parser/output/table_regions.json` – table detection metadata

## 4. Ingest into Postgres (with embeddings)

Once `parsed_document.json` exists, run the ingestion/embedding script. It loads the JSON, generates embeddings (unless you skip them), and persists everything via `rag/ingestion.DatabaseWriter`.

```bash
uv run python parser/src/scripts/run_embeddings.py
```

## 5. Interact with the FastAPI RAG service

Key endpoints exposed:

- `POST /query` – RAG workflow answering natural-language questions
- `GET /search` – hybrid semantic/keyword search of ingested sections
- `GET /sections/{section_number}` – retrieve a specific section
- `POST /v1/chat/completions` – OpenAI-compatible endpoint used by NextChat
