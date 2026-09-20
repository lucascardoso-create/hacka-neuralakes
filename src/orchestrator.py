from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .analysis_agent import AnalysisAgent
from .llm_provider import LLMProvider
from .research_agent import ResearchAgent
from .schemas import AuditEvent, ResearchPlan, ResearchState, StructuredDemand


class OrchestratorAgent:
    """Agente Orquestrador do Sistema Jurídico.
    
    Responsabilidades:
    - Gerenciamento do ciclo de vida da execução e máquina de estados.
    - Ingestão, validação e normalização da demanda inicial.
    - Coordenação sequencial entre o Agente de Pesquisa e o Agente de Análise.
    - Registro de auditoria, tratamento de contingências e geração do manifesto final.
    """

    def __init__(
        self,
        research_agent: ResearchAgent | None = None,
        analysis_agent: AnalysisAgent | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.provider = provider or LLMProvider()
        self.research_agent = research_agent or ResearchAgent(provider=self.provider)
        self.analysis_agent = analysis_agent or AnalysisAgent(provider=self.provider)

    def audit(self, state: ResearchState, node: str, message: str) -> list[dict]:
        """Registra um evento formal de auditoria no estado."""
        return [*state.get("audit", []), AuditEvent(node=node, message=message).model_dump()]

    def normalize_demand(self, state: ResearchState) -> dict:
        """Normaliza os dados explícitos da demanda jurídica inicial."""
        demand_text = state.get("original_demand", "")
        prompt = (
            "Extraia apenas dados explícitos da demanda jurídica inicial.\n"
            "Preencha o resumo fático, teses jurídicas, pedidos e magistrado/vara se presentes.\n\n"
            f"DEMANDA: {demand_text}"
        )
        try:
            structured = self.provider.structured(
                "Extraia dados explícitos e retorne JSON estritamente válido.",
                prompt,
                StructuredDemand,
            )
            message = "Demanda normalizada com sucesso pelo LLM"
        except RuntimeError as exc:
            structured = StructuredDemand(summary=demand_text)
            message = f"Normalização determinística de contingência: {exc}"

        return {
            "structured_demand": structured.model_dump(),
            "audit": self.audit(state, "orchestrator_normalize", message),
        }

    def run_pipeline(
        self,
        original_demand: str,
        document_limit: int = 3,
        run_id: str | None = None,
        mode: str = "live",
    ) -> ResearchState:
        """Executa o pipeline completo coordenando os 3 agentes."""
        active_run_id = run_id or str(uuid4())
        state: ResearchState = {
            "run_id": active_run_id,
            "original_demand": original_demand,
            "document_limit": document_limit,
            "documents": [],
            "errors": [],
            "audit": [],
            "status": "running",
        }

        # 1. Orquestrador: Normalização
        state.update(self.normalize_demand(state))

        # 2. Agente de Pesquisa: Plano
        demand = StructuredDemand.model_validate(state["structured_demand"])
        plan, plan_msg = self.research_agent.create_plan(demand, document_limit=document_limit)
        state["research_plan"] = plan.model_dump()
        state["audit"] = self.audit(state, "research_plan", plan_msg)

        # 3. Agente de Pesquisa: Coleta e Download
        output_dir = Path("outputs") / "runs" / active_run_id / "documents"
        docs, research_errors, research_msg = self.research_agent.collect(
            plan=plan,
            output_dir=output_dir,
            mode=mode,
        )
        state["documents"] = [doc.model_dump() for doc in docs]
        state["errors"] = [*state.get("errors", []), *research_errors]
        state["audit"] = self.audit(state, "research_collect", research_msg)

        # 4. Agente de Análise: Leitura, Rubrica e Parecer
        assessment, analysis_msg = self.analysis_agent.evaluate(
            original_demand=original_demand,
            documents=state["documents"],
        )
        state["assessment"] = assessment.model_dump()
        state["audit"] = self.audit(state, "analysis_evaluate", analysis_msg)

        # 5. Orquestrador: Finalização e Manifesto
        expected = plan.document_limit
        is_success = len(docs) >= expected and bool(state.get("assessment")) and not state.get("errors")
        state["status"] = "completed" if is_success else "failed"
        state["audit"] = self.audit(
            state,
            "orchestrator_finalize",
            f"Execução finalizada: {len(docs)}/{expected} documentos coletados (status: {state['status']})",
        )

        # Salva manifesto em disco
        manifest_path = Path("outputs") / "runs" / active_run_id / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        return state
