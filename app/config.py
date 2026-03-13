from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Your Gemini API key — set this in the .env file
    gemini_api_key: str

    # Model to use. gemini-2.5-flash is fast and free-tier friendly.
    model_name: str = "gemini-2.5-flash"

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

    class Config:
        env_file = ".env"


settings = Settings()
