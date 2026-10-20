from fastapi import FastAPI
from app.api.ask import router as ask_router
from app.api.health import router as health_router
from app.api.repos import router as repos_router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="Repo Mind", version="0.2.0")
app.include_router(health_router)
app.include_router(repos_router)
app.include_router(ask_router)