from __future__ import annotations

import subprocess
import time
from hashlib import md5
from pathlib import Path
from shutil import which

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.models import DeploymentRun, GeneratedArtifact, GenerationRun
from app.domain.enums.common import ArtifactType, ProjectStatus, RunStatus, TaskType
from app.infrastructure.storage.artifact_storage import ArtifactStorage
from app.services.projects import ProjectService
from app.utils.dates import utc_now


class DeploymentService:
    def __init__(
        self,
        db: Session,
        storage: ArtifactStorage,
        project_service: ProjectService,
        settings: Settings,
    ) -> None:
        self.db = db
        self.storage = storage
        self.project_service = project_service
        self.settings = settings

    def deploy(self, *, project_id: str, approved: bool, dry_run: bool) -> DeploymentRun:
        if not approved:
            raise ValueError("Требуется подтверждение пользователя перед деплоем")
        generation_run = self._latest_code_generation(project_id)
        output_payload = dict(generation_run.output_payload)
        snapshot_root = Path(str(output_payload.get("snapshot_root", "")))
        compose_path = snapshot_root / "docker-compose.generated.yml"
        if not snapshot_root.exists() or not compose_path.exists():
            raise ValueError("Не найден snapshot сгенерированного приложения. Сначала выполните генерацию кода.")

        deployment = DeploymentRun(
            project_id=project_id,
            status=RunStatus.RUNNING.value,
            dry_run=dry_run,
            logs="Подготовка deployment bundle",
        )
        self.db.add(deployment)
        self.db.commit()
        self.db.refresh(deployment)
        deployment.target_path = str(snapshot_root)
        preview_url = str(output_payload.get("preview_url", ""))
        logs = [
            "Deployment snapshot selected",
            f"Snapshot root: {snapshot_root}",
            f"Compose path: {compose_path}",
        ]
        try:
            command_base = self._compose_command()
            logs.append(f"Compose command: {' '.join(command_base)}")
            if not Path("/var/run/docker.sock").exists():
                logs.append("Docker socket не смонтирован в backend-контейнер. Real deploy не сможет работать.")
            if dry_run:
                result = self._run_subprocess(
                    [*command_base, "-f", str(compose_path), "config"],
                    cwd=snapshot_root,
                    timeout=60,
                )
                logs.extend(self._render_process_logs(result))
                if result.returncode != 0:
                    deployment.status = RunStatus.FAILED.value
                else:
                    logs.append("Dry-run mode enabled. Compose file is valid.")
                    if preview_url:
                        logs.append(f"Preview URL after real deploy: {preview_url}")
                    deployment.status = RunStatus.COMPLETED.value
            else:
                project_suffix = md5(project_id.encode("utf-8")).hexdigest()[:8]
                result = self._run_subprocess(
                    [
                        *command_base,
                        "-p",
                        f"case_generated_{project_suffix}",
                        "-f",
                        str(compose_path),
                        "up",
                        "-d",
                        "--build",
                    ],
                    cwd=snapshot_root,
                    timeout=240,
                )
                logs.extend(self._render_process_logs(result))
                if result.returncode != 0:
                    deployment.status = RunStatus.FAILED.value
                else:
                    healthy, health_url = self._wait_for_health(preview_url)
                    logs.append(
                        f"Healthcheck {'passed' if healthy else 'failed'} for {health_url or preview_url or 'unknown url'}"
                    )
                    deployment.status = RunStatus.COMPLETED.value if healthy else RunStatus.FAILED.value
        except Exception as exc:
            logs.append(str(exc))
            deployment.status = RunStatus.FAILED.value
        deployment.logs = "\n".join(logs)
        deployment.finished_at = utc_now()
        self.db.add(deployment)
        self.db.add(
            GeneratedArtifact(
                project_id=project_id,
                artifact_type=ArtifactType.DEPLOYMENT_BUNDLE.value,
                name=compose_path.name,
                path=str(compose_path),
                version=1,
                size_bytes=compose_path.stat().st_size,
            )
        )
        self.db.commit()
        if deployment.status == RunStatus.COMPLETED.value:
            self.project_service.update_status(project_id, ProjectStatus.DEPLOYED)
        else:
            self.project_service.update_status(project_id, ProjectStatus.FAILED)
        return deployment

    def _latest_code_generation(self, project_id: str) -> GenerationRun:
        run = self.db.scalar(
            select(GenerationRun)
            .where(
                GenerationRun.project_id == project_id,
                GenerationRun.task_type == TaskType.CODE_GENERATION.value,
                GenerationRun.status == RunStatus.COMPLETED.value,
            )
            .order_by(GenerationRun.started_at.desc())
            .limit(1)
        )
        if run is None:
            raise ValueError("Нет завершённой генерации кода для деплоя")
        return run

    def _wait_for_health(self, preview_url: str) -> tuple[bool, str]:
        if not preview_url:
            return False, ""
        candidate_urls = self._healthcheck_candidates(preview_url)
        for _ in range(40):
            for candidate_url in candidate_urls:
                try:
                    response = httpx.get(candidate_url, timeout=3.0, follow_redirects=True)
                    if response.status_code < 400:
                        return True, candidate_url
                except Exception:
                    continue
            time.sleep(1)
        return False, candidate_urls[0]

    def _healthcheck_candidates(self, preview_url: str) -> list[str]:
        base_url = preview_url.rstrip("/")
        candidates = [
            f"{base_url}/api/health",
            f"{base_url}/health",
            f"{base_url}/",
            f"{base_url}/index.html",
        ]
        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                deduped.append(candidate)
                seen.add(candidate)
        return deduped

    def _compose_command(self) -> list[str]:
        docker_binary = which("docker")
        if docker_binary is not None:
            probe = self._run_subprocess([docker_binary, "compose", "version"], cwd=Path.cwd(), timeout=15)
            if probe.returncode == 0:
                return [docker_binary, "compose"]
        compose_binary = which("docker-compose")
        if compose_binary is not None:
            probe = self._run_subprocess([compose_binary, "version"], cwd=Path.cwd(), timeout=15)
            if probe.returncode == 0:
                return [compose_binary]
        raise ValueError(
            "В backend-окружении не найден рабочий docker compose. Убедитесь, что контейнер пересобран и имеет доступ к Docker CLI."
        )

    def _run_subprocess(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def _render_process_logs(self, result: subprocess.CompletedProcess[str]) -> list[str]:
        logs = [f"Exit code: {result.returncode}"]
        if result.stdout:
            logs.append("STDOUT:")
            logs.append(result.stdout)
        if result.stderr:
            logs.append("STDERR:")
            logs.append(result.stderr)
        return logs
