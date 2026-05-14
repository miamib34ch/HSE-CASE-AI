from fastapi import APIRouter, Depends, HTTPException

from app.agents.orchestrator import AgentOrchestrator
from app.api.deps import get_agent_orchestrator, get_provider_registry
from app.providers.registry import ProviderRegistry
from app.schemas.agents import AgentExecuteRequest

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
def list_agents(
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
) -> list[dict[str, object]]:
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role,
            "approval_mode": agent.approval_mode,
            "enabled": agent.enabled,
        }
        for agent in orchestrator.list_agents()
    ]


@router.post("/execute")
def execute_agent(
    payload: AgentExecuteRequest,
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> dict[str, object]:
    try:
        execution = orchestrator.execute(
            project_id=payload.project_id,
            agent_name=payload.agent_name,
            task=payload.task,
            payload=payload.payload,
            approved=payload.approved,
            adapter=registry.get(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"execution_id": execution.id, "status": execution.status, "logs": execution.logs}
