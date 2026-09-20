from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from .browser_use import BrowserUseClient, BrowserUseError
from .llm_provider import LLMProvider
from .schemas import DownloadedDocument, ResearchPlan, StructuredDemand


class ResearchAgent:
    """Agente de Pesquisa Judicial e Coleta de Decisões.
    
    Responsabilidades:
    - Elaboração de plano de busca jurídica (termos, juiz, vara e limites).
    - Conexão e navegação automatizada no TJSP CJPG via Browser Use Cloud.
    - Download seguro, validação de integridade e registro das decisões (PDFs).
    - Suporte a modo live (busca real na web) e replay (evidências prévias em disco).
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or LLMProvider()

    def create_plan(
        self,
        demand: StructuredDemand,
        document_limit: int = 3,
    ) -> tuple[ResearchPlan, str]:
        """Gera o plano de pesquisa formal com base na demanda estruturada."""
        prompt = (
            "Você é um pesquisador jurídico sênior especializado em jurisprudência do TJSP.\n"
            "Crie um plano de pesquisa de sentenças com base na demanda fornecida.\n"
            "Priorize decisões do mesmo juiz e vara quando especificados.\n"
            f"Use critérios objetivos de similaridade e retorne document_limit igual a {document_limit}.\n\n"
            f"DEMANDA: {demand.model_dump_json()}"
        )
        try:
            plan = self.provider.structured(
                "Retorne somente JSON válido de acordo com o schema.",
                prompt,
                ResearchPlan,
            )
            message = "Plano de pesquisa produzido pelo LLM"
        except RuntimeError as exc:
            plan = ResearchPlan(
                query=demand.summary,
                judge=demand.target_judge,
                court=demand.target_court,
                similarity_criteria=["mesma tese jurídica", "mesmo pedido", "mesmo julgador quando disponível"],
                document_limit=document_limit,
            )
            message = f"Plano de pesquisa determinístico: {exc}"

        # Garante que o limite seja o definido pela execução
        plan = plan.model_copy(update={"document_limit": document_limit})
        return plan, message

    def collect(
        self,
        plan: ResearchPlan,
        output_dir: str | Path,
        mode: str = "live",
    ) -> tuple[list[DownloadedDocument], list[str], str]:
        """Executa a coleta das decisões no TJSP e salva os PDFs no diretório de destino."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # Modo replay: se houver PDFs já salvos no diretório ou em cache
        if mode == "replay":
            existing_pdfs = list(out_path.glob("*.pdf"))
            if existing_pdfs:
                docs = [
                    DownloadedDocument(
                        case_id=p.stem,
                        title=f"Decisão TJSP — {p.stem}",
                        source_url="",
                        local_path=str(p.resolve()),
                        sha256="",
                        text_excerpt="",
                        judge=plan.judge,
                        court=plan.court,
                        similarity_reason="Evidência reutilizada via modo replay",
                        similarity_score=1.0,
                    )
                    for p in existing_pdfs
                ]
                return docs, [], f"{len(docs)} documento(s) carregado(s) via replay"

        client: BrowserUseClient | None = None
        docs: list[DownloadedDocument] = []
        errors: list[str] = []
        warning: str | None = None

        try:
            client = BrowserUseClient()
            docs = client.search_and_download(plan, str(out_path))
        except BrowserUseError as exc:
            exc_msg = str(exc)
            partial = client.last_result.get("results", []) if (client and client.last_result) else []
            if partial:
                warning = exc_msg
                errors.append(exc_msg)
            else:
                return [], [exc_msg], f"Falha na pesquisa judicial: {exc_msg}"
        finally:
            if client is not None:
                client.stop_last_browser()

        audit_msg = f"{len(docs)} documento(s) coletado(s) pelo Agente de Pesquisa"
        if warning:
            audit_msg += f" (aviso: {warning})"

        return docs, errors, audit_msg
