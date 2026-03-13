from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Your Gemini API key — set this in the .env file
    gemini_api_key: str

    # Model to use. gemini-2.5-flash is fast and free-tier friendly.
    model_name: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"


settings = Settings()
