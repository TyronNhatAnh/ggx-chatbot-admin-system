from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Your Gemini API key — set this in the .env file
    gemini_api_key: str

    # Model to use. gemini-flash-latest is fast and free-tier friendly.
    model_name: str = "gemini-flash-latest"

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
    # /chat endpoint guardrails
    # ---------------------------------------------------------------------------
    chat_auth_enabled: bool = True
    chat_api_key: str = ""
    chat_rate_limit_enabled: bool = True
    chat_rate_limit_requests: int = 30
    chat_rate_limit_window_seconds: int = 60
    chat_order_cache_ttl_seconds: int = 60

    # Allow extra keys in .env (e.g. repo/branch vars used by Makefile only)
    # without failing Settings validation at runtime.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
