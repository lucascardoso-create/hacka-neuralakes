from __future__ import annotations

from pathlib import Path

from .analysis_agent import AnalysisAgent
from .orchestrator import OrchestratorAgent
from .research_agent import ResearchAgent
from .schemas import AuditEvent, DemandAssessment, ResearchPlan, ResearchState, StructuredDemand


def _audit(state: ResearchState, node: str, message: str) -> list[dict]:
    return [*state.get("audit", []), AuditEvent(node=node, message=message).model_dump()]


# --- NÓS DO AGENTE ORQUESTRADOR ---

def normalize_demand(state: ResearchState) -> dict:
    """Nó do Agente Orquestrador: normalização e estruturação da demanda."""
    orchestrator = OrchestratorAgent()
    return orchestrator.normalize_demand(state)


def finalize(state: ResearchState) -> dict:
    """Nó do Agente Orquestrador: finalização, status e auditoria."""
    errors = state.get("errors", [])
    documents = state.get("documents", [])
    plan_dict = state.get("research_plan", {})
    expected = plan_dict.get("document_limit", 3) if plan_dict else 3
    status = "completed" if len(documents) >= expected and state.get("assessment") and not errors else "failed"
    return {
        "status": status,
        "audit": _audit(state, "finalize", f"Execução finalizada com {len(documents)}/{expected} documentos (status: {status})"),
    }


# --- NÓS DO AGENTE DE PESQUISA ---

def create_research_plan(state: ResearchState) -> dict:
    """Nó do Agente de Pesquisa: formulação do plano de busca no TJSP."""
    demand = StructuredDemand.model_validate(state["structured_demand"])
    document_limit = int(state.get("document_limit", 3))
    agent = ResearchAgent()
    plan, message = agent.create_plan(demand, document_limit=document_limit)
    return {
        "research_plan": plan.model_dump(),
        "audit": _audit(state, "create_research_plan", message),
    }


def research(state: ResearchState) -> dict:
    """Nó do Agente de Pesquisa: busca e download dos PDFs no TJSP."""
    import os
    plan = ResearchPlan.model_validate(state["research_plan"])
    output_dir = Path("outputs") / "runs" / state["run_id"] / "documents"
    agent = ResearchAgent()
    mode = state.get("mode") or os.getenv("RESEARCH_MODE") or ("replay" if os.getenv("OFFLINE_MODE") == "true" else "live")
    docs, errors, message = agent.collect(plan, output_dir=output_dir, mode=mode)
    return {
        "documents": [doc.model_dump() for doc in docs],
        "errors": [*state.get("errors", []), *errors],
        "audit": _audit(state, "research", message),
    }


# --- NÓS DO AGENTE DE ANÁLISE ---

def assess_demand(state: ResearchState) -> dict:
    """Nó do Agente de Análise: extração de texto, rubrica jurídica e parecer."""
    agent = AnalysisAgent()
    assessment, message = agent.evaluate(
        original_demand=state.get("original_demand", ""),
        documents=state.get("documents", []),
    )
    return {
        "assessment": assessment.model_dump(),
        "audit": _audit(state, "assess_demand", message),
    }
