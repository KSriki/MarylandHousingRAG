"""Central configuration, overridable by environment variables.

Every knob that differs between local dev and production lives here so no
package hardcodes a connection string or a model name. Loaded once and
passed down (imperative shell), keeping the pure core testable.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MDHPP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Postgres / pgvector -------------------------------------------------
    pg_host: str = Field("localhost")
    pg_port: int = Field(5432)
    pg_db: str = Field("mdhpp")
    pg_user: str = Field("mdhpp")
    pg_password: str = Field("mdhpp")

    # --- Embedding + rerank models (behind the model port) -------------------
    embedding_model: str = Field("BAAI/bge-m3")
    embedding_dim: int = Field(1024)
    reranker_model: str = Field("BAAI/bge-reranker-v2-m3")

    # --- Chunking ------------------------------------------------------------
    chunk_size_tokens: int = Field(400)
    chunk_overlap_tokens: int = Field(60)

    # --- Retrieval -----------------------------------------------------------
    retrieve_top_k: int = Field(20)
    rerank_top_k: int = Field(5)
    relevance_floor: float = Field(
        0.30, description="Below this rerank score, refuse rather than guess."
    )

    # --- Generation ----------------------------------------------------------
    llm_provider: str = Field("ollama", description="ollama | openai | anthropic")
    llm_model: str = Field("llama3.1:8b")
    llm_temperature: float = Field(0.1)
    llm_host: str = Field(
        "http://localhost:11434",
        description=(
            "LLM server URL. In Docker on Mac/Windows, set to "
            "http://host.docker.internal:11434 to reach Ollama on the host."
        ),
    )

    # --- Guardrail -----------------------------------------------------------
    disclaimer: str = Field(
        "This is informational only and not legal advice. "
        "Consult a licensed Maryland attorney for your situation."
    )

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )


def load_settings() -> Settings:
    """Single entry point so callers don't construct Settings ad hoc."""
    return Settings()
