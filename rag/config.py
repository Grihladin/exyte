"""Application configuration powered by environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic.v1 import BaseSettings
from pydantic import Field

# Load .env file automatically when this module is imported.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)


class Settings(BaseSettings):
    """Strongly-typed configuration for the RAG system."""

    # Database
    database_url: str = Field(default="", env="DATABASE_URL")
    postgres_host: str = Field("localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(55432, env="POSTGRES_PORT")
    postgres_user: str = Field("rag_user", env="POSTGRES_USER")
    postgres_password: str = Field("rag_password", env="POSTGRES_PASSWORD")
    postgres_db: str = Field("building_codes", env="POSTGRES_DB")

    # OpenAI / LLM
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    embedding_model: str = Field("text-embedding-3-small", env="EMBEDDING_MODEL")
    chat_model: str = Field("gpt-4o", env="CHAT_MODEL")

    # Retrieval defaults
    top_k_sections: int = Field(5, alias="TOP_K_SECTIONS")
    hybrid_search_weight: float = Field(0.7, alias="HYBRID_SEARCH_WEIGHT")

    # LangGraph defaults
    max_iterations: int = Field(5, alias="MAX_ITERATIONS")
    temperature: float = Field(0.1, alias="TEMPERATURE")

    # pydantic BaseSettings populates fields from env variables (see Field(..., env="...") above)
    class Config:
        env_file = str(Path(__file__).resolve().parent.parent / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        """Backfill DATABASE_URL if it is not explicitly provided."""

        if not self.database_url:
            self.database_url = (
                f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()


settings = get_settings()
