from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_provider_registry
from app.providers.registry import ProviderRegistry

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck(
    db: Session = Depends(get_db),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    provider = registry.get()
    return {"status": "ok", "database": "ok", "provider": provider.healthcheck()}
