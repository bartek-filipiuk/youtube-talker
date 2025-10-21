"""
Application Configuration

Centralized configuration management using Pydantic Settings.
All configuration is loaded from environment variables.
"""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings are type-checked and validated by Pydantic.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Settings
    ENV: str = "development"
    DEBUG: bool = True

    # Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5435/youtube_talker"

    # Qdrant Configuration
    QDRANT_URL: str = "http://localhost:6335"
    QDRANT_API_KEY: str = ""

    # OpenRouter API Configuration (LLM completions)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_CLAUDE_MODEL: str = "anthropic/claude-haiku-4.5"
    OPENROUTER_GEMINI_MODEL: str = "google/gemini-2.5-flash"
    OPENROUTER_SITE_URL: str = "http://localhost:8000"
    OPENROUTER_SITE_NAME: str = "YoutubeTalker"

    # OpenAI API Configuration (Embeddings)
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # SUPADATA API Configuration
    SUPADATA_API_KEY: str = ""
    SUPADATA_BASE_URL: str = "https://api.supadata.ai"

    # RAG Configuration
    RAG_TOP_K: int = 12
    RAG_CONTEXT_MESSAGES: int = 10
    CHUNK_SIZE: int = 700
    CHUNK_OVERLAP_PERCENT: int = 20

    # Authentication & Security
    SESSION_EXPIRES_DAYS: int = 7
    SECRET_KEY: str = "your_secret_key_here_change_in_production"

    # CORS Configuration
    ALLOWED_ORIGINS: str = "http://localhost:4321,http://localhost:3000"

    # LangSmith Configuration (Optional)
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "youtube-talker"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


# Global settings instance
settings = Settings()
