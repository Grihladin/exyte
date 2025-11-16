"""FastAPI server for the RAG system."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag.api.routes import openai_compat, query, search, sections
from rag.config import settings
from rag.database.connection import close_pool, get_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle events."""
    # Startup
    logger.info("Starting RAG API server")
    logger.info(
        f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
    logger.info(f"Embedding model: {settings.embedding_model}")
    logger.info(f"Chat model: {settings.chat_model}")

    # Initialize connection pool
    try:
        pool = get_pool()
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down RAG API server")
    close_pool()
    logger.info("Database connection pool closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance with all routes,
        middleware, and error handlers registered.
    """
    app = FastAPI(
        title="Building Code RAG API",
        version="0.2.0",
        description="Retrieval-Augmented Generation API for building code queries.",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "message": (
                    str(exc)
                    if settings.model_config.get("debug")
                    else "An unexpected error occurred"
                ),
            },
        )

    # Health check endpoint
    @app.get("/health", tags=["system"])
    async def health_check():
        """Check API health status."""
        return {
            "status": "healthy",
            "database": "connected" if get_pool() else "disconnected",
            "openai_configured": settings.is_openai_configured,
        }

    # Root endpoint
    @app.get("/", tags=["system"])
    async def root():
        """API information."""
        return {
            "name": "Building Code RAG API",
            "version": "0.2.0",
            "description": "Retrieval-Augmented Generation API for building code queries",
            "endpoints": {
                "query": "/query",
                "search": "/search",
                "sections": "/sections",
                "chat": "/v1/chat/completions",
                "models": "/v1/models",
                "health": "/health",
            },
        }

    # Include routers
    app.include_router(openai_compat.router)  # OpenAI-compatible for NextChat
    app.include_router(query.router)
    app.include_router(search.router)
    app.include_router(sections.router)

    return app


app = create_app()
