import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Multishot Continuity Engine API"
    API_V1_PREFIX: str = "/api/v1"

    # For local dev you can use sqlite:
    # SQLALCHEMY_DATABASE_URI: str = "sqlite:///./app.db"
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL", "sqlite:///./app.db"
    )

    class Config:
        env_file = ".env"


settings = Settings()