import os
from pydantic_settings import BaseSettings

from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Multishot Continuity Engine API"
    API_V1_PREFIX: str = "/api/v1"

    # For local dev you can use sqlite:
    # SQLALCHEMY_DATABASE_URI: str = "sqlite:///./app.db"
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL", "sqlite:///./app.db"
    )

    GOOGLE_CLOUD_PROJECT_ID: str
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    
    # Runway ML Configuration
    RUNWAY_API_KEY: str = os.getenv("RUNWAY_ML_API_KEY", "")
    
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-2")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "ai-video-consistency")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()