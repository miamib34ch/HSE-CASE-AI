from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self, *, event_type: str, correlation_id: str, project_id: str | None = None, details: dict[str, object] | None = None
    ) -> AuditEvent:
        audit_event = AuditEvent(
            project_id=project_id,
            event_type=event_type,
            correlation_id=correlation_id,
            details=details or {},
        )
        self.db.add(audit_event)
        self.db.commit()
        self.db.refresh(audit_event)
        return audit_event

