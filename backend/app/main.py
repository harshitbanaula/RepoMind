from fastapi import FastAPI
from app.api.health import router as health_router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="Repo Copilot", version="0.1.0")
app.include_router(health_router)