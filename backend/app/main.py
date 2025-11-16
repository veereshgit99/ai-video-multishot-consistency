from fastapi import FastAPI

from app.core.config import settings
from app.db import Base, engine
from app.api.routes import health, projects, characters, scenes

# Create DB tables on startup (for dev; later replace with Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)


app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
app.include_router(characters.router, prefix=settings.API_V1_PREFIX)
app.include_router(scenes.router, prefix=settings.API_V1_PREFIX)
