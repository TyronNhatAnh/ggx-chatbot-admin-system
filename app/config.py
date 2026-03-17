from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Your Gemini API key — set this in the .env file
    gemini_api_key: str

    # Model to use. gemini-3-flash is fast and free-tier friendly.
    model_name: str = "gemini-3-flash"

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
    # User Service credentials — used by AuthTokenManager to obtain a Bearer
    # token via POST /api/v1/auth/login.  Never commit real values.
    # ---------------------------------------------------------------------------
    user_service_phone_number: str  # e.g. "(+82)106083106"
    user_service_password: str
    user_service_type_cd: int = 1          # 1 = standard admin/operator account
    user_service_auth_mode: str = "MULTI_AUTH"

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
