from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (Supabase Postgres, pooled/transaction-mode connection string on port 6543)
    database_url: str

    # JWT auth
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24h, generous for an MVP

    # Amazon Bedrock (used by the Strands agent, not the API itself)
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "us.anthropic.claude-opus-4-6-v1"

    # Bedrock Guardrails — not wired up yet, reserved for a later iteration
    guardrail_id: str | None = None
    guardrail_version: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
