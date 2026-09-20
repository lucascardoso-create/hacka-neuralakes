from __future__ import annotations

from pathlib import Path

from .browser_use import BrowserUseClient, BrowserUseError
from .llm_provider import LLMProvider
from .schemas import AuditEvent, ResearchPlan, ResearchState, StructuredDemand


def _audit(state: ResearchState, node: str, message: str) -> list[dict]:
    return [*state.get("audit", []), AuditEvent(node=node, message=message).model_dump()]


def normalize_demand(state: ResearchState) -> dict:
    demand = state["original_demand"]
    provider = LLMProvider()
    try:
        structured = provider.structured(
            "Extraia apenas dados explícitos da demanda jurídica. Retorne JSON válido.",
            demand,
            StructuredDemand,
        )
    except RuntimeError as exc:
        # Modo offline mantém o grafo executável, sem fingir inferência do LLM.
        structured = StructuredDemand(summary=demand)
        message = f"Normalização determinística: {exc}"
    else:
        message = "Demanda normalizada pelo LLM"
    return {"structured_demand": structured.model_dump(), "audit": _audit(state, "normalize_demand", message)}


def create_research_plan(state: ResearchState) -> dict:
    demand = StructuredDemand.model_validate(state["structured_demand"])
    document_limit = int(state.get("document_limit", 10))
    provider = LLMProvider()
    prompt = (
        "Crie um plano de pesquisa de sentenças. Priorize decisões do mesmo juiz e vara; "
        f"use critérios objetivos de similaridade; retorne document_limit igual a {document_limit}.\n\n"
        f"Demanda: {demand.model_dump_json()}"
    )
    try:
        plan = provider.structured("Retorne somente JSON válido.", prompt, ResearchPlan)
    except RuntimeError as exc:
        plan = ResearchPlan(
            query=demand.summary,
            judge=demand.target_judge,
            court=demand.target_court,
            similarity_criteria=["mesma tese", "mesmo pedido", "mesmo julgador quando disponível"],
        )
        message = f"Plano determinístico: {exc}"
    else:
        message = "Plano de pesquisa produzido pelo LLM"
    # O limite é decisão explícita de quem executa o fluxo; o LLM não pode ampliá-lo.
    plan = plan.model_copy(update={"document_limit": document_limit})
    return {"research_plan": plan.model_dump(), "audit": _audit(state, "create_research_plan", message)}


def research(state: ResearchState) -> dict:
    plan = ResearchPlan.model_validate(state["research_plan"])
    output_dir = Path("outputs") / "runs" / state["run_id"] / "documents"
    output_dir.mkdir(parents=True, exist_ok=True)
    client: BrowserUseClient | None = None
    try:
        client = BrowserUseClient()
        docs = client.search_and_download(plan, str(output_dir))
    except BrowserUseError as exc:
        return {
            "documents": [],
            "errors": [*state.get("errors", []), str(exc)],
            "audit": _audit(state, "research", "Browser Use não retornou PDFs verificáveis"),
        }
    finally:
        if client is not None:
            client.stop_last_browser()
    return {"documents": [doc.model_dump() for doc in docs], "audit": _audit(state, "research", f"{len(docs)} documentos retornados")}


def finalize(state: ResearchState) -> dict:
    errors = state.get("errors", [])
    documents = state.get("documents", [])
    expected = ResearchPlan.model_validate(state["research_plan"]).document_limit
    status = "completed" if len(documents) >= expected and not errors else "failed"
    return {"status": status, "audit": _audit(state, "finalize", f"Execução finalizada com {len(documents)}/{expected} documentos")}
