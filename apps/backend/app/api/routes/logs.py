from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import AuditEvent, MCPInvocationLog

router = APIRouter(tags=["logs"])


@router.get("/audit")
def list_audit_events(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)))
    return [
        {
            "id": event.id,
            "project_id": event.project_id,
            "event_type": event.event_type,
            "actor": event.actor,
            "details": event.details,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]


@router.get("/mcp/invocations")
def list_mcp_invocations(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    items = list(
        db.scalars(select(MCPInvocationLog).order_by(MCPInvocationLog.created_at.desc()).limit(200))
    )
    return [
        {
            "id": item.id,
            "server_id": item.server_id,
            "tool_name": item.tool_name,
            "request_payload": item.request_payload,
            "response_payload": item.response_payload,
            "status": item.status,
            "correlation_id": item.correlation_id,
        }
        for item in items
    ]

