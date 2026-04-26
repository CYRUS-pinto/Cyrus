"""
Cyrus — Application Configuration
All settings loaded from environment variables (or .env file).
Using pydantic-settings for type-safe, validated configuration.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────
    app_name: str = "Cyrus"
    environment: Literal["development", "production"] = "development"
    secret_key: str = "change-me-in-production"

    # ── Database ─────────────────────────────────────────────
    # For cloud (PostgreSQL): postgresql+asyncpg://user:pass@host/db
    # For local (SQLite):     sqlite+aiosqlite:///./cyrus.db
    database_url: str = "sqlite+aiosqlite:///./cyrus.db"

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── MinIO / Object Storage ───────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "cyrus-files"
    minio_secure: bool = False

    # Supabase Storage (cloud fallback — leave blank for MinIO)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # ── Ollama (local AI) ────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_grading_model: str = "mistral:7b-instruct-q4_K_M"
    ollama_vision_model: str = "llava:7b-q4_K_M"
    ollama_embed_model: str = "nomic-embed-text"

    # ── Groq (cloud fallback) ────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # ── OCR ─────────────────────────────────────────────────
    ocr_mode: Literal["ensemble", "trocr_only", "cloud"] = "ensemble"
    ocr_confidence_threshold: float = 0.7
    ocr_finetune_threshold: int = 200   # corrections needed to enable fine-tuning

    # ── Email (Resend) ───────────────────────────────────────
    resend_api_key: str = ""
    email_from: str = "noreply@cyrus.app"

    # ── Google Sheets ────────────────────────────────────────
    google_service_account_json: str = ""

    # ── Security ─────────────────────────────────────────────
    admin_pin: str = ""   # optional — leave blank for open access
    share_token_expiry_days: int = 7

    # ── CORS Origins ─────────────────────────────────────────
    @property
    def cors_origins(self) -> list[str]:
        if self.environment == "development":
            return ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"]
        return ["https://cyrus.app"]   # replace with your actual domain


@lru_cache()
def get_settings() -> Settings:
    """
    Returns the application settings (singleton via lru_cache).
    The lru_cache means this function only creates the Settings object once.
    All subsequent calls return the same instance — no repeated env file reads.
    """
    return Settings()
