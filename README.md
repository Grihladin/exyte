# Building Code RAG Platform

An end-to-end toolkit for turning the 2021 International Building Code into a searchable Retrieval-Augmented Generation (RAG) assistant. The stack includes:

- **Parser pipeline** that extracts sections, tables, and figures from the official PDF.
- **Ingestion and embedding jobs** that normalize the parsed data and store it in Postgres with pgvector.
- **FastAPI service** exposing native query/search endpoints plus an OpenAI-compatible `/v1/chat/completions` route for LibreChat and other clients.
- **LibreChat UI** preconfigured to talk to the local RAG API.
- **Static document hosting** so citations rendered in the UI deep-link into the source PDF.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)  
2. [Repository Layout](#repository-layout)  
3. [Prerequisites](#prerequisites)  
4. [Environment Configuration](#environment-configuration)  
5. [Quick Start with Docker Compose](#quick-start-with-docker-compose)  
6. [Manual Workflow (Parser ➜ DB ➜ API)](#manual-workflow-parser--db--api)  
7. [LibreChat Integration](#librechat-integration)  
8. [RAG API Reference](#rag-api-reference)  
9. [Static Document Hosting & Citation Links](#static-document-hosting--citation-links)  

---

## Architecture Overview

```
┌────────────┐      ┌─────────────┐      ┌─────────────┐      ┌──────────────┐
│  Parser    │ ---> │  Ingestion  │ ---> │  Postgres   │ ---> │   RAG API    │
│ (PDF → JSON│      │ + Embedding │      │ + pgvector  │      │ (FastAPI +   │
│ + assets)  │      │             │      │             │      │ LangGraph)   │
└────────────┘      └─────────────┘      └─────────────┘      └──────────────┘
                                                                    │
                                                                    ▼
                                                           LibreChat (OpenAI API)
                                                                    │
                                                                    ▼
                                                        Static PDF (clickable refs)
```

1. `parser/` extracts structured data from the PDF and saves it in `parser/output/`.
2. `rag/ingestion/` loads that JSON, generates embeddings (OpenAI by default), and writes the results into Postgres with pgvector.
3. `rag/api/` contains a FastAPI app with:
   - `/query`, `/search`, `/sections` REST endpoints
   - `/v1/chat/completions` OpenAI-compatible endpoint used by LibreChat.
4. `LibreChat/` (git submodule) provides the UI. The bundled config points to the RAG API and strips unused features.
5. `static/` serves the source PDF through FastAPI so citations in chat responses open the correct page.

---

## Repository Layout

| Path | Purpose |
|------|---------|
| `parser/` | PDF parsing pipeline, models, helper scripts |
| `rag/` | Ingestion jobs, database schema, LangGraph workflow, FastAPI server |
| `static/2021_International_Building_Code.pdf` | Default source PDF, also mounted for the UI |
| `LibreChat/` | LibreChat UI (submodule) configured for the custom endpoint |
| `librechat.config.yaml` | Minimal LibreChat configuration pre-wired to the local API |
| `docker-compose.yml` | Postgres + RAG API + LibreChat stack |
| `pyproject.toml`, `uv.lock` | Python 3.12 project definition |

---

## Environment Configuration

1. Copy the sample file and edit to match your environment:

   ```bash
   cp .env.example .env
   ```

2. Important variables:

   `OPENAI_API_KEY` Required for embeddings + LLM answers
   `Weights & Biases setup` Required for [`wandb.ai`](https://wandb.ai/site/)

3. If you cloned without the LibreChat submodule:

   ```bash
   git submodule update --init --recursive
   ```

---

## Quick Start with Docker Compose

The Compose file launches:

| Service | Description | Ports |
|---------|-------------|-------|
| `postgres` | Postgres 16 + pgvector, auto-seeded with schema | `${POSTGRES_PORT:-55432}` |
| `rag-api` | FastAPI app exposing REST + OpenAI-compatible endpoints | `${API_PORT:-8000}` |
| `librechat-mongo` | MongoDB backing store for LibreChat | internal |
| `librechat` | LibreChat UI/API talking to `rag-api` | `${LIBRECHAT_PORT:-3080}` |

Bring everything up:

```bash
docker compose up --build   # foreground
docker compose up -d        # background
```


Health checks ensure `postgres` is ready before the API starts, and LibreChat waits for both the API and Mongo.

When the stack is running:

- API docs & health: http://localhost:8000/docs and `/health`
- LibreChat UI: http://localhost:3080
- Static PDF (for citations): http://localhost:8000/static/2021_International_Building_Code.pdf

---

2. **Parse the PDF**

   ```bash
   uv run python parser/src/scripts/run_parser.py
   ```

   Outputs land in `parser/output/`:

   - `parsed_document.json` – canonical data set for ingestion
   - `images/`, `tables/` – extracted assets
   - `table_regions.json` – table detection metadata

3. **Embed & ingest**

   ```bash
   uv run python parser/src/scripts/run_embeddings.py
   ```

   This writes sections, tables, figures, and embeddings to Postgres.

## LibreChat Integration

- `librechat.config.yaml` disables most modules (prompts, presets, search, agents) for a focused chat experience.
- The `BuildingCodeRAG` endpoint is defined as a **custom provider** with:
  - `baseURL`: `http://rag-api:8000/v1`
  - `model`: `building-code-rag`
  - `titleConvo: true` to auto-title conversations
  - `summarize: false` (set to `true` if you want automatic context summarization)
  - `dropParams` removing unsupported OpenAI parameters
- Update `librechat.config.yaml` to expose additional models or features if needed.
- When auth is enabled, LibreChat sends `Authorization: Bearer <LIBRECHAT_RAG_API_KEY>` and the FastAPI app verifies it against `RAG_API_KEY`.

---

## RAG API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health probe used by Compose and debugging |
| `/query` | POST | Runs the LangGraph workflow (retrieval + answering) |
| `/search` | GET | Hybrid keyword/vector search over ingested sections |
| `/sections/{section_number}` | GET | Fetch metadata for a specific section |
| `/v1/chat/completions` | POST | OpenAI-compatible endpoint used by LibreChat |
| `/v1/models` | GET | Lists the custom `building-code-rag` model |

Responses produced by `/query` and `/v1/chat/completions` include Markdown-formatted answers plus a “References” section. When `REFERENCE_URL_TEMPLATE` is configured, each citation becomes a clickable link to the host PDF.

---

## Static Document Hosting & Citation Links

- `static/2021_International_Building_Code.pdf` is copied into the Docker image and mounted by FastAPI at `/static`.
- Configure `REFERENCE_URL_TEMPLATE` (e.g. `http://localhost:8000/static/2021_International_Building_Code.pdf#page={page}`) so the backend can embed proper hyperlinks in its Markdown output.
- The same value is stored on each section/table/figure record as `url`, making it trivial for other clients to provide rich previews.
- If you need to serve additional files, drop them under `static/`

---
