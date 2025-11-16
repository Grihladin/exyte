"""FastAPI server for the RAG system."""

from __future__ import annotations

from fastapi import FastAPI

from rag.api.routes import query, search, sections


def create_app() -> FastAPI:
    app = FastAPI(title="Building Code RAG API", version="0.1.0")
    app.include_router(query.router)
    app.include_router(search.router)
    app.include_router(sections.router)
    return app


app = create_app()
