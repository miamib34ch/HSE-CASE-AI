from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, health, logs, mcp, mcp_server, projects, providers
from app.config.settings import get_settings
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware, InMemoryRateLimitMiddleware
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import engine

settings = get_settings()
configure_logging(settings.app_debug)
Path(settings.storage_root).mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HSE CASE AI",
    version="0.1.0",
    description="Прототип CASE-системы для автоматизации разработки с применением генеративного ИИ",
)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(providers.router, prefix="/api")
app.include_router(mcp.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(mcp_server.router)

@app.get("/")
def root() -> dict[str, str]:
    return {"message": "HSE CASE AI backend is running"}
