"""
Application Configuration

Centralized configuration management using Pydantic Settings.
All configuration is loaded from environment variables.
"""

from typing import List

from pydantic import model_validator
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
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_talker"

    # Qdrant Configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # OpenRouter API Configuration (LLM completions)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_CLAUDE_MODEL: str = "anthropic/claude-haiku-4.5"
    OPENROUTER_GEMINI_MODEL: str = "google/gemini-2.5-flash"
    OPENROUTER_KIMI_MODEL: str = "moonshotai/kimi-k2-thinking"
    OPENROUTER_GROK_MODEL: str = "x-ai/grok-4-fast"
    OPENROUTER_SITE_URL: str = "http://localhost:8000"
    OPENROUTER_SITE_NAME: str = "Qivio"

    # Available Models for Conversation Selection
    # These are the friendly names used in the UI and database
    AVAILABLE_MODELS: List[str] = [
        "claude-haiku-4.5",
        "gemini-2.5-flash",
        "kimi-k2-thinking",
        "grok-4-fast",
    ]
    DEFAULT_CONVERSATION_MODEL: str = "claude-haiku-4.5"

    # OpenAI API Configuration (Embeddings)
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # SUPADATA API Configuration
    SUPADATA_API_KEY: str = ""
    SUPADATA_BASE_URL: str = "https://api.supadata.ai"

    # RAG Configuration (Fallback defaults - prefer database config via ConfigService)
    # These values are used when ConfigService is unavailable (e.g., during setup)
    # Production code should load from ConfigService for dynamic configuration
    RAG_TOP_K: int = 12  # Database key: rag.top_k
    RAG_CONTEXT_MESSAGES: int = 10  # Database key: rag.context_messages
    CHUNK_SIZE: int = 700  # Database key: rag.chunk_size
    CHUNK_OVERLAP_PERCENT: int = 20  # Database key: rag.chunk_overlap_percent

    # Authentication & Security
    SESSION_EXPIRES_DAYS: int = 7
    SECRET_KEY: str = "your_secret_key_here_change_in_production"

    # CORS Configuration
    ALLOWED_ORIGINS: str = "http://localhost:4321,http://localhost:3000"

    # LangSmith Configuration (Optional)
    # Note: LangChain looks for LANGCHAIN_* env vars, not LANGSMITH_*
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "youtube-talker"
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://eu.api.smith.langchain.com"

    # Stripe Configuration
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_MONTHLY_PRICE_ID: str = ""
    STRIPE_PRO_ANNUAL_PRICE_ID: str = ""

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """
        Validate critical settings in production environment.

        Ensures that security-sensitive settings are properly configured
        before the application starts in production mode.

        Raises:
            ValueError: If SECRET_KEY is using default value in production
        """
        if self.ENV == "production":
            # Check SECRET_KEY is not default
            if self.SECRET_KEY == "your_secret_key_here_change_in_production":
                raise ValueError(
                    "SECRET_KEY must be changed from default value in production. "
                    "Set a secure random string in your .env file."
                )

            # Check required API keys are set
            if not self.OPENROUTER_API_KEY:
                raise ValueError(
                    "OPENROUTER_API_KEY must be set in production environment."
                )

            if not self.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY must be set in production environment."
                )

            if not self.SUPADATA_API_KEY:
                raise ValueError(
                    "SUPADATA_API_KEY must be set in production environment."
                )

        return self


# Global settings instance
settings = Settings()
