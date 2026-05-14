from pathlib import Path

import pytest
from app.config.settings import Settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.enums.common import ArtifactType
from app.infrastructure.storage.artifact_storage import ArtifactStorage
from app.providers.fake import FakeLLMAdapter
from app.services.artifacts import ArtifactService
from app.services.deployment import DeploymentService
from app.services.generation import GenerationService
from app.services.projects import ProjectService
from app.services.requirements import RequirementService
from app.services.site_scaffold import GeneratedFileEntry, extract_generated_file_entries
from app.services.testing import TestService
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def test_requirements_and_generation_flow(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    storage = ArtifactStorage(
        Settings(STORAGE_ROOT=tmp_path, DATABASE_URL="sqlite+pysqlite:///:memory:")
    )
    project_service = ProjectService(db)
    requirement_service = RequirementService(db, storage, project_service)
    generation_service = GenerationService(db, storage, project_service)
    test_service = TestService(db, storage, project_service)
    project = project_service.create_project(name="Demo", description="Desc")
    requirement_service.upload(
        project_id=project.id,
        content="Нужна система управления задачами с проектами и комментариями",
        source_type="markdown",
        filename="req.md",
    )
    structure = requirement_service.structure(
        project_id=project.id,
        adapter=FakeLLMAdapter(),
        model="demo-analysis-v1",
        correlation_id="test-correlation",
    )
    requirement_service.confirm(
        project_id=project.id,
        approved=True,
        markdown_content=structure.markdown_content,
        structured_json=structure.structured_json,
    )
    run = generation_service.generate_code(
        project_id=project.id,
        adapter=FakeLLMAdapter(),
        model="demo-code-v1",
        correlation_id="test-correlation",
        approved=True,
    )
    assert run.status == "completed"
    snapshot_root = Path(str(run.output_payload["snapshot_root"]))
    assert (snapshot_root / "docker-compose.generated.yml").exists()
    assert (snapshot_root / "backend" / "app" / "main.py").exists()
    test_run = test_service.generate_tests(
        project_id=project.id,
        adapter=FakeLLMAdapter(),
        model="demo-test-v1",
        approved=True,
    )
    assert test_run.passed == 5
    generated_artifacts = list(
        db.scalars(
            select(models.GeneratedArtifact).where(
                models.GeneratedArtifact.project_id == project.id,
                models.GeneratedArtifact.artifact_type == ArtifactType.GENERATED_TESTS.value,
            )
        )
    )
    assert generated_artifacts
    db.close()


def test_schema_generation_and_manual_artifacts(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    storage = ArtifactStorage(
        Settings(STORAGE_ROOT=tmp_path, DATABASE_URL="sqlite+pysqlite:///:memory:")
    )
    project_service = ProjectService(db)
    requirement_service = RequirementService(db, storage, project_service)
    generation_service = GenerationService(db, storage, project_service)
    artifact_service = ArtifactService(db, storage)
    project = project_service.create_project(name="Artifact Demo", description="Desc")
    requirement_service.upload(
        project_id=project.id,
        content="Нужна система с проектами, задачами и ролями",
        source_type="markdown",
        filename="req.md",
    )
    structure = requirement_service.structure(
        project_id=project.id,
        adapter=FakeLLMAdapter(),
        model="demo-analysis-v1",
        correlation_id="test-correlation",
    )
    requirement_service.confirm(
        project_id=project.id,
        approved=True,
        markdown_content=structure.markdown_content,
        structured_json=structure.structured_json,
    )

    schema_run = generation_service.generate_schemas(
        project_id=project.id,
        adapter=FakeLLMAdapter(),
        model="demo-analysis-v1",
        correlation_id="schema-correlation",
        approved=True,
    )

    assert schema_run.status == "completed"
    schema_artifacts = artifact_service.list_artifacts(project.id)
    assert any(artifact.artifact_type == ArtifactType.GENERATED_DIAGRAM.value for artifact in schema_artifacts)

    uploaded = artifact_service.upload_bytes(
        project_id=project.id,
        filename="business-process.md",
        content=b"# BPMN draft",
        artifact_type=ArtifactType.MANUAL_UPLOAD,
    )
    assert artifact_service.read_text_content(uploaded) == "# BPMN draft"

    updated = artifact_service.update_text_artifact(
        project_id=project.id,
        artifact_id=uploaded.id,
        content="# Updated BPMN draft",
    )
    assert updated.version == 2
    assert artifact_service.read_text_content(updated) == "# Updated BPMN draft"
    db.close()


def test_draft_requirements_from_description(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    storage = ArtifactStorage(
        Settings(STORAGE_ROOT=tmp_path, DATABASE_URL="sqlite+pysqlite:///:memory:")
    )
    project_service = ProjectService(db)
    requirement_service = RequirementService(db, storage, project_service)
    project = project_service.create_project(name="Draft Demo", description="Desc")

    document, structure = requirement_service.draft_from_description(
        project_id=project.id,
        description="Нужен сервис управления задачами, проектами, ролями и уведомлениями",
        adapter=FakeLLMAdapter(),
        model="demo-analysis-v1",
        correlation_id="draft-correlation",
        auto_structure=True,
    )

    assert "Функциональные требования" in document.content
    assert structure is not None
    assert "Task" in str(structure.structured_json.get("domain_entities"))
    db.close()


def test_delete_multiple_artifacts_sequentially(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    storage = ArtifactStorage(
        Settings(STORAGE_ROOT=tmp_path, DATABASE_URL="sqlite+pysqlite:///:memory:")
    )
    artifact_service = ArtifactService(db, storage)
    project_service = ProjectService(db)
    project = project_service.create_project(name="Delete Demo", description="Desc")

    first = artifact_service.upload_bytes(
        project_id=project.id,
        filename="first.md",
        content=b"# First",
        artifact_type=ArtifactType.MANUAL_UPLOAD,
    )
    second = artifact_service.upload_bytes(
        project_id=project.id,
        filename="second.md",
        content=b"# Second",
        artifact_type=ArtifactType.MANUAL_UPLOAD,
    )

    assert artifact_service.delete_artifact(project.id, first.id) is True
    assert artifact_service.delete_artifact(project.id, second.id) is True
    assert artifact_service.delete_artifact(project.id, second.id) is False
    assert artifact_service.list_artifacts(project.id) == []
    db.close()


def test_extract_generated_file_entries_supports_data_uri_images() -> None:
    payload = (
        '{"files":{"frontend/logo.png":{"data":"data:image/png;base64,SGVsbG8="},'
        '"frontend/index.html":"<html><body>ok</body></html>"}}'
    )
    entries = extract_generated_file_entries(payload)

    assert entries is not None
    assert entries["frontend/logo.png"].binary == b"Hello"
    assert entries["frontend/logo.png"].text is None
    assert entries["frontend/index.html"].text == "<html><body>ok</body></html>"


def test_validate_generated_site_files_requires_frontend_bundle(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    storage = ArtifactStorage(
        Settings(STORAGE_ROOT=tmp_path, DATABASE_URL="sqlite+pysqlite:///:memory:")
    )
    project_service = ProjectService(db)
    generation_service = GenerationService(db, storage, project_service)
    project_service.create_project(name="Bundle Demo", description="Desc")

    api_only_bundle = {
        "docker-compose.generated.yml": GeneratedFileEntry(
            text=(
                "services:\n"
                "  api:\n"
                "    build:\n"
                "      context: .\n"
                "      dockerfile: ./backend/Dockerfile\n"
                '    ports:\n      - "9114:3000"\n'
            )
        ),
        "backend/Dockerfile": GeneratedFileEntry(text="FROM node:20-alpine\n"),
    }

    with pytest.raises(ValueError, match="без пользовательского интерфейса"):
        generation_service._validate_generated_site_files(api_only_bundle)

    frontend_bundle = dict(api_only_bundle)
    frontend_bundle["frontend/index.html"] = GeneratedFileEntry(text="<html><body>Pizza</body></html>")
    generation_service._validate_generated_site_files(frontend_bundle)
    db.close()


def test_deployment_healthcheck_accepts_health_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    storage = ArtifactStorage(
        Settings(STORAGE_ROOT=tmp_path, DATABASE_URL="sqlite+pysqlite:///:memory:")
    )
    project_service = ProjectService(db)
    deployment_service = DeploymentService(
        db,
        storage,
        project_service,
        Settings(STORAGE_ROOT=tmp_path, DATABASE_URL="sqlite+pysqlite:///:memory:"),
    )

    class DummyResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    def fake_get(url: str, *, timeout: float, follow_redirects: bool) -> DummyResponse:
        assert timeout == 3.0
        assert follow_redirects is True
        if url.endswith("/api/health"):
            return DummyResponse(404)
        if url.endswith("/health"):
            return DummyResponse(200)
        return DummyResponse(500)

    monkeypatch.setattr("app.services.deployment.httpx.get", fake_get)
    ok, checked_url = deployment_service._wait_for_health("http://localhost:9114")

    assert ok is True
    assert checked_url == "http://localhost:9114/health"
    db.close()
