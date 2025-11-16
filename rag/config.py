"""Application configuration powered by environment variables."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Load .env file automatically when this module is imported.
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


class Settings(BaseSettings):
    """Strongly-typed configuration for the RAG system.

    All settings can be configured via environment variables.
    Defaults are provided for development, but production deployments
    should explicitly set all required values.
    """

    # ========================================================================
    # Database Configuration
    # ========================================================================
    database_url: str = Field(
        default="",
        description="Full PostgreSQL connection string. If not provided, "
        "constructed from individual postgres_* fields.",
    )
    postgres_host: str = Field(
        default="localhost", description="PostgreSQL server hostname"
    )
    postgres_port: int = Field(
        default=55432, ge=1, le=65535, description="PostgreSQL server port"
    )
    postgres_user: str = Field(
        default="rag_user", min_length=1, description="PostgreSQL username"
    )
    postgres_password: str = Field(
        default="rag_password", min_length=1, description="PostgreSQL password"
    )
    postgres_db: str = Field(
        default="building_codes", min_length=1, description="PostgreSQL database name"
    )

    # ========================================================================
    # LLM Configuration
    # ========================================================================
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key for embeddings and chat completions"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model name"
    )
    chat_model: str = Field(
        default="gpt-4o", description="OpenAI chat model for answer generation"
    )
    temperature: float = Field(
        default=0.1, ge=0.0, le=2.0, description="LLM temperature for answer generation"
    )

    # ========================================================================
    # Retrieval Configuration
    # ========================================================================
    top_k_sections: int = Field(
        default=5, ge=1, le=50, description="Default number of sections to retrieve"
    )
    hybrid_search_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight for vector search in hybrid search (0-1)",
    )

    # ========================================================================
    # Workflow Configuration
    # ========================================================================
    max_iterations: int = Field(
        default=5, ge=1, le=20, description="Maximum LangGraph workflow iterations"
    )

    # ========================================================================
    # Telemetry Configuration (Weights & Biases)
    # ========================================================================
    wandb_enabled: bool = Field(
        default=False, description="Enable Weights & Biases logging"
    )
    wandb_project: Optional[str] = Field(default=None, description="W&B project name")
    wandb_entity: Optional[str] = Field(
        default=None, description="W&B entity/team name"
    )
    wandb_run_name: Optional[str] = Field(
        default=None, description="W&B run name (auto-generated if not provided)"
    )

    # ========================================================================
    # API Configuration
    # ========================================================================
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    api_cors_origins: list[str] = Field(
        default=["*"], description="CORS allowed origins"
    )

    model_config = {
        "env_file": str(_env_path),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "validate_assignment": True,
    }

    @field_validator("openai_api_key", mode="after")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate OpenAI API key format."""
        if v and not v.startswith(("sk-", "user_provided")):
            logger.warning(
                "OpenAI API key does not start with 'sk-'. "
                "This may indicate an invalid key."
            )
        return v

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        """Construct DATABASE_URL if not explicitly provided."""
        if not self.database_url:
            self.database_url = (
                f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
            logger.debug("Constructed database_url from individual postgres settings")

    @property
    def is_openai_configured(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key and self.openai_api_key != "user_provided")

    @property
    def is_wandb_configured(self) -> bool:
        """Check if Weights & Biases is properly configured."""
        return self.wandb_enabled and bool(self.wandb_project)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton settings instance.

    This function is cached to ensure only one Settings instance exists,
    preventing multiple environment variable reads and database URL constructions.
    """
    return Settings()


# Global settings instance for convenient imports
settings = get_settings()
