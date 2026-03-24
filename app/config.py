from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Model to use — for Vertex AI use a versioned name e.g. gemini-2.0-flash-001
    # model_name: str = "gemini-2.0-flash-001"
    model_name: str = "gemini-2.5-flash"  # --- IGNORE ---

    # ---------------------------------------------------------------------------
    # Vertex AI service account credentials
    # ---------------------------------------------------------------------------
    vertex_ai_credentials_file: str = "app/config/vertex-ai.json"
    vertex_ai_sa_key: str = "gemini-kr-sa-staging"
    vertex_ai_location: str = "asia-northeast3"

    # ---------------------------------------------------------------------------
    # User Service — provides authentication (Bearer token)
    # Swagger: https://stag-api.gogox.co.kr/user/swagger/index.html
    # ---------------------------------------------------------------------------
    user_service_base_url: str = "https://stag-api.gogox.co.kr/user"

    # ---------------------------------------------------------------------------
    # Order Service — read-only order data
    # Swagger: https://stag-api.gogox.co.kr/order/swagger/index.html
    # ---------------------------------------------------------------------------
    order_service_base_url: str = "https://stag-api.gogox.co.kr/order"

    # ---------------------------------------------------------------------------
    # Driver Service — read-only driver data
    # Swagger: https://stag-api.gogox.co.kr/driver/swagger/index.html
    # ---------------------------------------------------------------------------
    driver_service_base_url: str = "https://stag-api.gogox.co.kr/driver"

    # ---------------------------------------------------------------------------
    # Common Service — read-only common data
    # Swagger: https://stag-api.gogox.co.kr/common/swagger/index.html
    # ---------------------------------------------------------------------------
    common_service_base_url: str = "https://stag-api.gogox.co.kr/common"

    # ---------------------------------------------------------------------------
    # /chat endpoint guardrails
    # ---------------------------------------------------------------------------
    chat_auth_enabled: bool = True
    chat_api_key: str = ""
    chat_rate_limit_enabled: bool = True
    chat_rate_limit_requests: int = 30
    chat_rate_limit_window_seconds: int = 60

    # ---------------------------------------------------------------------------
    # Chat history persistence
    # ---------------------------------------------------------------------------
    # Path to the SQLite database file for persisting chat history across
    # server restarts.  Leave empty (default) to keep the original in-memory-
    # only behaviour.
    chat_history_db: str = ""

    # ---------------------------------------------------------------------------
    # Vertex AI context caching
    # ---------------------------------------------------------------------------
    # Cache system_instruction + tool schemas on Vertex AI to reduce input token
    # cost by ~75% on the cached portion (tools ≈ 5k tokens + prompt ≈ 2k tokens).
    # Requires a VERSIONED model name, e.g. MODEL_NAME=gemini-2.0-flash-001
    # Aliases like "gemini-2.5-flash" are NOT supported for explicit caching.
    context_caching_enabled: bool = False

    # Allow extra keys in .env (e.g. repo/branch vars used by Makefile only)
    # without failing Settings validation at runtime.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
