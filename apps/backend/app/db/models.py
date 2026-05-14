from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums.common import (
    ApprovalMode,
    ArtifactType,
    ProjectStatus,
    RunStatus,
    TaskType,
    TransportType,
    TrustLevel,
)
from app.utils.dates import utc_now


def default_uuid() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default=ProjectStatus.DRAFT.value)


class RequirementDocument(Base, TimestampMixin):
    __tablename__ = "requirement_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32), default="text")
    filename: Mapped[str] = mapped_column(String(255), default="requirements.md")
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class RequirementItem(Base, TimestampMixin):
    __tablename__ = "requirement_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    requirement_document_id: Mapped[str] = mapped_column(ForeignKey("requirement_documents.id"))
    item_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)


class RequirementStructure(Base, TimestampMixin):
    __tablename__ = "requirement_structures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    requirement_document_id: Mapped[str] = mapped_column(ForeignKey("requirement_documents.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    structured_json: Mapped[dict[str, object]] = mapped_column(JSON)
    markdown_content: Mapped[str] = mapped_column(Text)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    task_type: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)


class GenerationRun(Base, TimestampMixin):
    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    task_type: Mapped[str] = mapped_column(String(64), default=TaskType.REQUIREMENTS_ANALYSIS.value)
    prompt_snapshot: Mapped[str] = mapped_column(Text)
    input_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    output_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.PENDING.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    correlation_id: Mapped[str] = mapped_column(String(64))


class GeneratedArtifact(Base, TimestampMixin):
    __tablename__ = "generated_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    generation_run_id: Mapped[str | None] = mapped_column(ForeignKey("generation_runs.id"), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(64), default=ArtifactType.GENERATED_CODE.value)
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1024))
    version: Mapped[int] = mapped_column(Integer, default=1)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)


class TestRun(Base, TimestampMixin):
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.PENDING.value)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    logs: Mapped[str] = mapped_column(Text, default="")
    junit_path: Mapped[str] = mapped_column(String(1024), default="")
    coverage_summary: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeploymentRun(Base, TimestampMixin):
    __tablename__ = "deployment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.PENDING.value)
    logs: Mapped[str] = mapped_column(Text, default="")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    target_path: Mapped[str] = mapped_column(String(1024), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    provider: Mapped[str] = mapped_column(String(64), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    config_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class LLMRequestLog(Base, TimestampMixin):
    __tablename__ = "llm_request_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    task_type: Mapped[str] = mapped_column(String(64))
    request_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(64))


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128))
    actor: Mapped[str] = mapped_column(String(128), default="system")
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64))


class MCPServerConnection(Base, TimestampMixin):
    __tablename__ = "mcp_server_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    transport_type: Mapped[str] = mapped_column(String(32), default=TransportType.STDIO.value)
    base_url: Mapped[str] = mapped_column(String(1024), default="")
    command: Mapped[str] = mapped_column(String(255), default="")
    args: Mapped[list[str]] = mapped_column(JSON, default=list)
    env: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    auth_type: Mapped[str] = mapped_column(String(32), default="none")
    auth_config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trust_level: Mapped[str] = mapped_column(String(32), default=TrustLevel.LOCAL_TRUSTED.value)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capabilities_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class MCPTool(Base, TimestampMixin):
    __tablename__ = "mcp_tools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    server_id: Mapped[str] = mapped_column(ForeignKey("mcp_server_connections.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    input_schema: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    side_effect: Mapped[bool] = mapped_column(Boolean, default=False)


class MCPResource(Base, TimestampMixin):
    __tablename__ = "mcp_resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    server_id: Mapped[str] = mapped_column(ForeignKey("mcp_server_connections.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    uri: Mapped[str] = mapped_column(String(1024))
    description: Mapped[str] = mapped_column(Text, default="")


class MCPPrompt(Base, TimestampMixin):
    __tablename__ = "mcp_prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    server_id: Mapped[str] = mapped_column(ForeignKey("mcp_server_connections.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    arguments_schema: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class MCPInvocationLog(Base, TimestampMixin):
    __tablename__ = "mcp_invocation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    server_id: Mapped[str] = mapped_column(ForeignKey("mcp_server_connections.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(255))
    request_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.PENDING.value)
    correlation_id: Mapped[str] = mapped_column(String(64))


class AgentProfile(Base, TimestampMixin):
    __tablename__ = "agent_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(255))
    system_prompt: Mapped[str] = mapped_column(Text)
    allowed_llm_providers: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_mcp_servers: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    execution_policy: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    approval_mode: Mapped[str] = mapped_column(String(32), default=ApprovalMode.ALWAYS.value)
    retry_policy: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentExecution(Base, TimestampMixin):
    __tablename__ = "agent_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_profile_id: Mapped[str | None] = mapped_column(ForeignKey("agent_profiles.id"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(64), default=TaskType.AGENT_EXECUTION.value)
    input_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.PENDING.value)
    logs: Mapped[str] = mapped_column(Text, default="")


class AgentToolPolicy(Base, TimestampMixin):
    __tablename__ = "agent_tool_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    agent_profile_id: Mapped[str] = mapped_column(ForeignKey("agent_profiles.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(255))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentHandoff(Base, TimestampMixin):
    __tablename__ = "agent_handoffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    from_agent: Mapped[str] = mapped_column(String(255))
    to_agent: Mapped[str] = mapped_column(String(255))
    artifact_refs: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")


class AgentMemorySnapshot(Base, TimestampMixin):
    __tablename__ = "agent_memory_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=default_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(255))
    snapshot_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
