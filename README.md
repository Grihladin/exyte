# Building Code RAG Platform

An end-to-end toolkit for turning the 2021 International Building Code into a searchable Retrieval-Augmented Generation (RAG) assistant.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)  
2. [System Overview](#system-overview--case-study-context)  
3. [Repository Layout](#repository-layout)  
4. [Environment Configuration](#environment-configuration)  
5. [Quick Start with Docker Compose](#quick-start-with-docker-compose)  
6. [RAG Pipeline](#rag-pipeline)  
7. [LibreChat Integration](#librechat-integration)  
8. [RAG API Reference](#rag-api-reference)  
9. [Static Document Hosting & Citation Links](#static-document-hosting--citation-links)  

---

## System Overview

This repository implements the **Document Intelligence & Compliance System** and the **Conversational AI Interface & Knowledge Assistant** for a construction-focused AI platform.

- Parses the 2021 International Building Code (IBC) into structured JSON (chapters, sections, tables, figures).
- Stores the normalized content in a **Postgres + pgvector** database.
- Exposes a **RAG (Retrieval-Augmented Generation) API** via FastAPI.
- Integrates with **LibreChat** to provide a chat-based assistant that can answer code/compliance questions with **grounded, cited answers**.

This module acts as the **building code knowledge backbone** that other components (e.g., drawing/blueprint analysis, risk assessment engine) can query for regulatory constraints and explanations.


## Architecture Overview
At a high level, the system consists of four main parts:

1. **Parsing Pipeline (`parser/`)**  
   - Extracts text, tables, and figures from the IBC PDF.  
   - Normalizes content into chapters, sections, table metadata, and image references.  
   - Outputs a single `parsed_document.json` artifact.

2. **RAG Ingestion (`rag/ingestion`)**  
   - Loads `parsed_document.json`.  
   - Chunks sections into retrieval units.  
   - Generates embeddings (via OpenAI or a compatible model).  
   - Persists sections + embeddings into Postgres with pgvector.

3. **RAG API (`rag/api`)**  
   - FastAPI service exposing:
     - `/query` – RAG pipeline endpoint.
     - `/search` – hybrid keyword / semantic search.
     - `/sections/{id}` – direct section retrieval.
     - `/v1/chat/completions` – OpenAI-compatible endpoint for LibreChat.

4. **Chat UI (LibreChat)**  
   - Front-end UI for human users.  
   - Sends OpenAI-compatible chat requests to the local RAG API.  
   - Displays model responses with citations back into the building code.

---

## RAG Pipeline

### Ingestion Flow

1. **PDF → Parsed JSON**  
   - `run_parser.py` processes the IBC PDF into `parsed_document.json`.

2. **JSON → Embeddings + DB**  
   - `run_embeddings.py` loads the parsed document, chunks it into retrieval units, calls the embedding model, and writes:
     - `sections`
     - `embeddings`
     - optional `tables` / `figures` metadata  
     into Postgres with pgvector.

### Query Flow

1. User asks a question in LibreChat or via `/query`.
2. The RAG API:
   - Embeds the query.
   - Performs a vector similarity search combined with keyword filters.
   - Ranks and selects a small set of relevant sections.
3. The selected sections are passed as **grounding context** to the LLM.
4. The LLM generates an answer **with inline citations** pointing back to the original IBC sections.
5. The answer and retrieval metadata are logged for future evaluation and auditing.


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
