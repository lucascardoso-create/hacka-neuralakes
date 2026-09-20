import time
from datetime import datetime, timezone
from pathlib import Path

from .analysis_agent import AnalysisAgent
from .debate_agent import DebateAgent
from .orchestrator import OrchestratorAgent
from .research_agent import ResearchAgent
from .schemas import AuditEvent, DemandAssessment, ResearchPlan, ResearchState, StructuredDemand


def _audit(state: ResearchState, node: str, message: str, duration_ms: float | None = None) -> list[dict]:
    event = AuditEvent(
        node=node,
        message=message,
        timestamp=datetime.now(timezone.utc).isoformat(),
        duration_ms=duration_ms,
    )
    return [*state.get("audit", []), event.model_dump()]


# --- NÓS DO AGENTE ORQUESTRADOR ---

def normalize_demand(state: ResearchState) -> dict:
    """Nó do Agente Orquestrador: normalização e estruturação da demanda."""
    t0 = time.perf_counter()
    orchestrator = OrchestratorAgent()
    res = orchestrator.normalize_demand(state)
    dur = round((time.perf_counter() - t0) * 1000, 2)
    audit = res.get("audit", state.get("audit", []))
    if audit:
        audit[-1]["duration_ms"] = dur
        if not audit[-1].get("timestamp"):
            audit[-1]["timestamp"] = datetime.now(timezone.utc).isoformat()
    return res


def finalize(state: ResearchState) -> dict:
    """Nó do Agente Orquestrador: finalização, status e auditoria."""
    t0 = time.perf_counter()
    errors = state.get("errors", [])
    documents = state.get("documents", [])
    plan_dict = state.get("research_plan", {})
    expected = plan_dict.get("document_limit", 3) if plan_dict else 3
    status = "completed" if len(documents) >= expected and state.get("assessment") and not errors else "failed"
    dur = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "status": status,
        "audit": _audit(
            state,
            "finalize",
            f"Execução finalizada com {len(documents)}/{expected} documentos (status: {status})",
            duration_ms=dur,
        ),
    }


# --- NÓS DO AGENTE DE PESQUISA ---

def create_research_plan(state: ResearchState) -> dict:
    """Nó do Agente de Pesquisa: formulação do plano de busca no TJSP."""
    t0 = time.perf_counter()
    demand = StructuredDemand.model_validate(state["structured_demand"])
    document_limit = int(state.get("document_limit", 3))
    agent = ResearchAgent()
    plan, message = agent.create_plan(demand, document_limit=document_limit)
    dur = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "research_plan": plan.model_dump(),
        "audit": _audit(state, "create_research_plan", message, duration_ms=dur),
    }


def research(state: ResearchState) -> dict:
    """Nó do Agente de Pesquisa: busca e download dos PDFs no TJSP."""
    t0 = time.perf_counter()
    import os
    plan = ResearchPlan.model_validate(state["research_plan"])
    output_dir = Path("outputs") / "runs" / state["run_id"] / "documents"
    agent = ResearchAgent()
    mode = state.get("mode") or os.getenv("RESEARCH_MODE") or ("replay" if os.getenv("OFFLINE_MODE") == "true" else "live")
    docs, errors, message = agent.collect(plan, output_dir=output_dir, mode=mode)
    dur = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "documents": [doc.model_dump() for doc in docs],
        "errors": [*state.get("errors", []), *errors],
        "audit": _audit(state, "research", message, duration_ms=dur),
    }


# --- NÓS DO AGENTE DE ANÁLISE ---

def assess_demand(state: ResearchState) -> dict:
    """Nó do Agente de Análise: extração de texto, rubrica jurídica e parecer."""
    t0 = time.perf_counter()
    agent = AnalysisAgent()
    assessment, message = agent.evaluate(
        original_demand=state.get("original_demand", ""),
        documents=state.get("documents", []),
    )
    dur = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "assessment": assessment.model_dump(),
        "audit": _audit(state, "assess_demand", message, duration_ms=dur),
    }


# --- NÓS DO DEBATE MULTI-AGENTE (A2A) ---

def debate_analysis(state: ResearchState) -> dict:
    """Nó de Debate Jurídico Multi-Agente (A2A): diálogo entre Defensor e Auditor de Riscos."""
    t0 = time.perf_counter()
    assessment_dict = state.get("assessment", {})
    if not assessment_dict:
        return {}

    agent = DebateAgent()
    comparisons = assessment_dict.get("comparisons", [])
    report_md = assessment_dict.get("report_markdown", "")

    turns, updated_report = agent.conduct_debate(
        original_demand=state.get("original_demand", ""),
        comparisons=comparisons,
        current_report=report_md,
    )

    assessment_dict["debate"] = [t.model_dump() for t in turns]
    assessment_dict["report_markdown"] = updated_report
    dur = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "assessment": assessment_dict,
        "audit": _audit(
            state,
            "debate_analysis",
            "Debate dialético multi-agente (A2A) realizado com sucesso entre Dra. Helena e Dr. Marcos",
            duration_ms=dur,
        ),
    }


