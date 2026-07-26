from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (Neon Postgres, pooled/transaction-mode connection string on port 6543)
    database_url: str

    # CORS. Comma-separated list of allowed browser origins. Locally this covers
    # the Next.js dev server and the static chat UI; in production set it to the
    # Amplify domain (e.g. "https://main.d123.amplifyapp.com,https://harmonyacres.com").
    cors_allow_origins: str = "http://localhost:3000,http://localhost:8000"

    # Which identity system is authoritative.
    #   "legacy"  -> the old bcrypt password + self-signed JWT flow (default for
    #                local dev; /auth/register and /auth/login work as before).
    #   "cognito" -> tokens are Cognito's; the backend only verifies them and the
    #                legacy /auth endpoints are disabled (set this in App Runner).
    auth_mode: str = "legacy"

    # --- Cognito ---
    # The User Pool is the identity provider now. The backend no longer signs
    # tokens; it *verifies* the JWTs Cognito issues, against the pool's public
    # JWKS. These are safe to expose (they're in every token's issuer URL).
    cognito_region: str = "us-east-1"
    cognito_user_pool_id: str = ""
    # The App Client the frontend logs in through. Access tokens carry this as
    # `client_id`; ID tokens carry it as `aud`. We verify against it.
    cognito_app_client_id: str = ""

    # --- Legacy JWT auth (kept only for the migration Lambda's DB verify path) ---
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24

    # Weekly ordering cycle. Deliveries land on Wednesday; drafts lock the
    # evening before so there's a full day to place the consolidated order with
    # the farm. Configurable because the farm's own cutoff has moved before.
    delivery_weekday: int = 2  # Monday=0 ... Sunday=6
    deadline_weekday: int = 1  # Tuesday
    deadline_hour_utc: int = 23

    # Amazon Bedrock (used by the Strands agent, not the API itself)
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "us.anthropic.claude-opus-4-6-v1"

    # ARN of the deployed AgentCore Runtime, obtained after `agentcore deploy`
    agent_runtime_arn: str = ""

    # AgentCore Memory resource ID (short-term conversation history), obtained
    # after `agentcore deploy` provisions the memory resource
    agent_memory_id: str = ""

    # Bedrock Guardrails — not wired up yet, reserved for a later iteration
    guardrail_id: str | None = None
    guardrail_version: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
