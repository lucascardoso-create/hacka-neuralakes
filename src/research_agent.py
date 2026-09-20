from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path
from typing import Sequence

from pypdf import PdfReader

from .browser_use import BrowserUseClient, BrowserUseError
from .llm_provider import LLMProvider
from .schemas import DownloadedDocument, ResearchPlan, StructuredDemand

# Mapeamento conhecido para PDFs de demonstração/benchmark
SAMPLE_METADATA = {
    "01_doc_133923819": {
        "case_id": "1023372-41.2022.8.26.0405",
        "title": "Sentença - Contratos Bancários",
        "judge": "ANTONIO MARCELO CUNZOLO RIMOLA",
        "court": "8ª Vara Cível - Foro de Osasco",
    },
    "02_doc_82580423": {
        "case_id": "1002937-34.2022.8.26.0506",
        "title": "Sentença - Indenização por Dano Moral",
        "judge": "ANTONIO MARCELO CUNZOLO RIMOLA",
        "court": "5ª Vara Cível - Foro de Ribeirão Preto",
    },
    "03_doc_87336637": {
        "case_id": "0013922-19.2007.8.26.0405",
        "title": "Sentença - Execução Hipotecária SFH",
        "judge": "ANTONIO MARCELO CUNZOLO RIMOLA",
        "court": "5ª Vara Cível - Foro de Osasco",
    },
}


class ResearchAgent:
    """Agente de Pesquisa Judicial e Coleta de Decisões.
    
    Responsabilidades:
    - Elaboração de plano de busca jurídica (termos, juiz, vara e limites).
    - Conexão e navegação automatizada no TJSP CJPG via Browser Use Cloud.
    - Download seguro, validação de integridade e registro das decisões (PDFs).
    - Suporte a modo live (busca real na web) e replay/test (evidências prévias em disco).
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
                judge=demand.target_judge or "ANTONIO MARCELO CUNZOLO RIMOLA",
                court=demand.target_court,
                similarity_criteria=["mesma tese jurídica", "mesmo pedido", "mesmo julgador quando disponível"],
                document_limit=document_limit,
            )
            message = f"Plano de pesquisa determinístico: {exc}"

        # Garante que o limite seja o definido pela execução
        plan = plan.model_copy(update={"document_limit": document_limit})
        return plan, message

    def _extract_case_id_from_pdf(self, pdf_path: Path) -> str:
        """Tenta extrair o número do processo unificado (CNJ) do texto do PDF."""
        try:
            reader = PdfReader(str(pdf_path))
            first_page = reader.pages[0].extract_text() or ""
            match = re.search(r"\b\d{7}-\d{2}\.\d{4}\.8\.26\.\d{4}\b", first_page)
            if match:
                return match.group(0)
        except Exception:
            pass
        return pdf_path.stem

    def collect(
        self,
        plan: ResearchPlan,
        output_dir: str | Path,
        mode: str = "live",
    ) -> tuple[list[DownloadedDocument], list[str], str]:
        """Executa a coleta das decisões no TJSP e salva os PDFs no diretório de destino."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        is_replay = mode in {"replay", "test"} or os.getenv("RESEARCH_MODE", "").lower() in {"replay", "test"}

        # Modo replay / teste com fixture local
        if is_replay:
            candidate_files = list(out_path.glob("*.pdf"))
            if not candidate_files:
                # Procura no diretório padrão de amostras
                sample_dirs = [
                    Path("outputs") / "sample_documents",
                    Path("outputs") / "demo" / "documents",
                    Path("outputs") / "pdf_collection",
                ]
                for s_dir in sample_dirs:
                    if s_dir.is_dir():
                        for p in s_dir.glob("*.pdf"):
                            dest = out_path / p.name
                            if not dest.exists():
                                shutil.copy2(p, dest)
                candidate_files = list(out_path.glob("*.pdf"))

            if candidate_files:
                docs: list[DownloadedDocument] = []
                for p in sorted(candidate_files)[: plan.document_limit]:
                    data = p.read_bytes()
                    sha256 = hashlib.sha256(data).hexdigest()
                    meta = SAMPLE_METADATA.get(p.stem, {})
                    case_id = meta.get("case_id") or self._extract_case_id_from_pdf(p)
                    title = meta.get("title", f"Sentença TJSP — {case_id}")
                    judge = meta.get("judge", plan.judge)
                    court = meta.get("court", plan.court)

                    docs.append(
                        DownloadedDocument(
                            case_id=case_id,
                            title=title,
                            source_url="https://esaj.tjsp.jus.br/cjpg/",
                            local_path=str(p.resolve()),
                            sha256=sha256,
                            text_excerpt="",
                            judge=judge,
                            court=court,
                            similarity_reason="Decisão recuperada no modo de validação/replay do TJSP",
                            similarity_score=1.0,
                        )
                    )
                return docs, [], f"{len(docs)} documento(s) carregado(s) via modo de validação/replay (Browser Use fixture)"

        # Modo LIVE: Chama o Browser Use Cloud real
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

        audit_msg = f"{len(docs)} documento(s) coletado(s) pelo Agente de Pesquisa via Browser Use"
        if warning:
            audit_msg += f" (aviso: {warning})"

        return docs, errors, audit_msg
