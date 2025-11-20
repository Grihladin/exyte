# Building Code Parser & RAG Stack

This repository contains everything needed to parse the 2021 International Building Code PDF, normalize the contents (chapters, sections, tables, figures), load the data into a pgvector powered Postgres database, and expose a Retrieval-Augmented Generation (RAG) API that can be paired with the bundled LibreChat UI. The core goals are:

- Fully reproducible parsing of the source PDF into structured JSON (`parser/`)
- Embedding and persistence pipelines that populate Postgres (`rag/ingestion`)
- A FastAPI service that serves search/query endpoints and an OpenAI-compatible chat interface (`rag/api`)
- A front-end experience powered by LibreChat (`LibreChat/` submodule)

## Repository layout

```
parser/               PDF parsing pipeline, models, and utilities
rag/                  RAG ingestion pipeline, database schema, API, and LangGraph workflow
LibreChat/            LibreChat UI (git submodule) configured to hit the local RAG API
librechat.config.yaml Minimal LibreChat configuration that targets the local OpenAI-compatible API
docker-compose.yml    Postgres (with pgvector) + API service definition
static/2021_International_Building_Code.pdf   Default parsing target (also served to UI)
pyproject.toml, uv.lock                Python project definition (Python 3.12)
```

## Prerequisites

- Python 3.12.x (the repo uses [`uv`](https://github.com/astral-sh/uv) but `pip` works too)
- Node.js 18+ (for optional local LibreChat development)
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

If you previously cloned without `--recurse-submodules`, run `git submodule update --init --recursive` to pull `LibreChat/`.

## 2. Start the stack with Docker Compose

The Compose file now orchestrates four services:

- `postgres` – Postgres 16 with pgvector plus the schema migrations under `rag/database`
- `rag-api` – builds from the repo `Dockerfile` and exposes the FastAPI RAG server
- `librechat-mongo` – MongoDB backing store required by LibreChat
- `librechat` – builds the LibreChat UI/API and proxies OpenAI-compatible traffic to the local RAG API

Bring the full stack online with:

```bash
docker compose up --build
# or keep it running in the background
docker compose up -d
```

- Postgres listens on `${POSTGRES_PORT:-55432}`
- FastAPI is available on http://localhost:${API_PORT:-8000}
- LibreChat is available on http://localhost:${LIBRECHAT_PORT:-3080}

Compose reads `.env`, so you can pin all of the container ports and LibreChat overrides in one place. LibreChat is configured through the tracked `librechat.config.yaml` file, which is mounted directly into the container via `CONFIG_PATH`. Environment variables referenced in that file (for example `LIBRECHAT_RAG_BASE_URL` and `LIBRECHAT_RAG_API_KEY`) must exist in your `.env`.

### LibreChat configuration

The default `librechat.config.yaml` strips the UI down to bare chat functionality and configures a single OpenAI-compatible endpoint that points at `rag-api`. Copy `.env.example` to `.env` and adjust the `LIBRECHAT_*` values to suit your environment. The base URL should include `/v1` because LibreChat sends `/chat/completions` to that path verbatim. Set `LIBRECHAT_RAG_API_KEY` to the same value as `RAG_API_KEY` if you want LibreChat to authenticate against the `/v1` endpoints; otherwise leave both empty to disable auth entirely.

Most LibreChat functionality (prompts, presets, agents, social auth, shared links, web search, etc.) is turned off by default. If you need to re-enable any of those modules you can modify `librechat.config.yaml` or override the relevant environment variables in `.env`. Registration is disabled out of the box; flip `LIBRECHAT_ALLOW_REGISTRATION=true` temporarily if you need to self-serve account creation.

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
- `POST /v1/chat/completions` – OpenAI-compatible endpoint used by LibreChat
