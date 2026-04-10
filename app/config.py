import os
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class _YamlConfigSource(PydanticBaseSettingsSource):
    """Load non-secret config from app/config/{APP_ENV}/config.yml."""

    def get_field_value(self, field: Any, field_name: str) -> Any:  # noqa: ANN401
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        app_env = os.environ.get("APP_ENV", "").strip()
        if not app_env:
            return {}
        yaml_path = Path(__file__).parent / "config" / app_env / "config.yml"
        if not yaml_path.exists():
            return {}
        with yaml_path.open() as f:
            return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    # Active environment — drives which app/config/{app_env}/config.yml is loaded.
    # Set via APP_ENV env var (e.g. stag, prod). Leave empty for local/.env-only mode.
    app_env: str = ""

    # Primary model (Flash) — low latency, low cost, good for tool-calling & lookups.
    # gemini-3-flash-preview is available on Vertex AI in: global, us-central1
    model_name: str = "gemini-3-flash-preview"

    # Optional Pro model for complex queries (codebase analysis).
    # When set, feature key "knowledge-code" is routed here.
    # Leave empty to use model_name for all queries.
    # gemini-3.1-pro-preview is available on Vertex AI in: global, us-central1
    pro_model_name: str = "gemini-3.1-pro-preview"

    # ---------------------------------------------------------------------------
    # Vertex AI service account credentials
    # ---------------------------------------------------------------------------
    vertex_ai_credentials_file: str = "app/config/vertex-ai.json"
    vertex_ai_sa_key: str = "gemini-kr-sa-staging"
    vertex_ai_location: str = "global"  # Gemini 3 preview models only available in: global, us-central1

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
    # Chat history persistence — Redis required in all environments.
    # ---------------------------------------------------------------------------
    redis_url: str = ""

    # SQLite fallback — legacy, not used. Leave empty.
    chat_history_db: str = ""

    # ---------------------------------------------------------------------------
    # Vertex AI context caching
    # ---------------------------------------------------------------------------
    # Cache system_instruction + tool schemas on Vertex AI to reduce input token
    # cost by ~75% on the cached portion (tools ≈ 5k tokens + prompt ≈ 2k tokens).
    # Requires a VERSIONED model name, e.g. MODEL_NAME=gemini-2.0-flash-001
    # Aliases like "gemini-3-flash-preview" are NOT supported for explicit caching.
    context_caching_enabled: bool = False

    # extra="ignore" so Makefile-only vars (repo paths etc.) don't break startup.
    model_config = SettingsConfigDict(extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority (highest → lowest): init kwargs → env vars → YAML config → field defaults
        # dotenv (.env file) is intentionally excluded — all config comes from YAML.
        return (init_settings, env_settings, _YamlConfigSource(settings_cls), file_secret_settings)


settings = Settings()
