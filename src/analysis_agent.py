from __future__ import annotations

from pathlib import Path
from typing import Sequence

from pypdf import PdfReader
from pydantic import BaseModel

from .document_parser import parse_judgment_pdf
from .llm_provider import LLMProvider
from .schemas import (
    DemandAssessment,
    EvidenceComparison,
    RepetitivenessAssessment,
    SuccessAssessment,
)


class ComparisonSet(BaseModel):
    comparisons: list[EvidenceComparison]


class AnalysisAgent:
    """Agente de Análise Jurídica e Avaliação de Evidências.
    
    Responsabilidades:
    - Extração resiliente e estruturada de texto dos PDFs das decisões judiciais.
    - Leitura jurídica comparativa por rubrica multi-eixo (fatos, tese, pedido, fase).
    - Aplicação de regras determinísticas de consolidação (limiar 65% e quórum de 3 sentenças).
    - Emissão de parecer estruturado e síntese executiva com citações e limites.
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or LLMProvider()

    def extract_text_from_pdf(self, file_path: str, max_characters: int = 3500) -> str:
        """Extrai texto e seções-chave da sentença (Relatório, Fundamentação, Dispositivo) via parser."""
        return parse_judgment_pdf(file_path, max_characters=max_characters)

    def evaluate(self, original_demand: str, documents: Sequence[dict]) -> tuple[DemandAssessment, str]:
        """Executa a avaliação jurídica completa da demanda contra a lista de documentos coletados."""
        evidence: list[dict] = []
        for doc in documents:
            local_path = str(doc.get("local_path", ""))
            text = self.extract_text_from_pdf(local_path)
            if text:
                evidence.append({
                    "evidence_id": doc.get("case_id") or doc.get("sha256") or Path(local_path).stem,
                    "judge": doc.get("judge"),
                    "court": doc.get("court"),
                    "text": text,
                })

        if not evidence:
            assessment = DemandAssessment(
                repetitividade=RepetitivenessAssessment(
                    label="inconclusivo",
                    probability=None,
                    rationale="Não há PDF com texto extraível para comparação jurídica.",
                ),
                exito=SuccessAssessment(
                    probability=None,
                    rationale="Não há decisão extraída para embasar a estimativa de êxito.",
                ),
                limitations=["PDFs utilizáveis: 0"],
            )
            return assessment, "Análise abstida: nenhum PDF extraível"

        prompt = (
            "Você é um analista jurídico sênior especializado em triagem de demandas de massa.\n"
            "Leia cada sentença judicial fornecida e compare-a individualmente com a demanda da autora.\n\n"
            "Retorne um JSON com o campo 'comparisons' contendo a lista de avaliações para cada evidence_id:\n"
            "{\n"
            '  "comparisons": [\n'
            "    {\n"
            '      "evidence_id": "ID_DO_DOCUMENTO",\n'
            '      "factual_match": 0.0 a 1.0,\n'
            '      "legal_match": 0.0 a 1.0,\n'
            '      "requested_outcome_match": 0.0 a 1.0,\n'
            '      "procedural_match": 0.0 a 1.0,\n'
            '      "material_differences": ["diferenca 1", "diferenca 2"],\n'
            '      "outcome": "favorable" | "unfavorable" | "mixed" | "unknown",\n'
            '      "outcome_basis": "explicacao do resultado",\n'
            '      "excerpts": ["trecho 1", "trecho 2"]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"DEMANDA ORIGINAL:\n{original_demand[:30_000]}\n\n"
            f"DOCUMENTOS JUDICIAIS COLETADOS:\n{evidence}"
        )

        try:
            comparison_set = self.provider.structured(
                "Você é analista jurídico sênior. Isto é apoio à triagem e exige revisão humana.",
                prompt,
                ComparisonSet,
            )
            valid_ids = {str(row["evidence_id"]) for row in evidence}
            valid_comparisons = [item for item in comparison_set.comparisons if item.evidence_id in valid_ids]
            assessment = self.consolidate_comparisons(valid_comparisons, len(evidence))
            message = f"{len(valid_comparisons)} sentença(s) comparada(s) por rubrica; consolidação determinística aplicada"
        except Exception as exc:
            assessment = DemandAssessment(
                repetitividade=RepetitivenessAssessment(
                    label="inconclusivo",
                    probability=None,
                    rationale="A inferência do LLM não pôde ser validada.",
                ),
                exito=SuccessAssessment(
                    probability=None,
                    rationale="A inferência do LLM não pôde ser validada.",
                ),
                limitations=[str(exc)],
            )
            message = f"Análise abstida: {exc}"

        return assessment, message

    def consolidate_comparisons(
        self,
        comparisons: list[EvidenceComparison],
        total_documents: int,
    ) -> DemandAssessment:
        """Aplica a política determinística de consolidação pós-leitura."""
        weighted: list[tuple[EvidenceComparison, float]] = []
        for item in comparisons:
            score = (
                item.factual_match * 0.35
                + item.legal_match * 0.30
                + item.requested_outcome_match * 0.25
                + item.procedural_match * 0.10
            )
            if score >= 0.65:
                weighted.append((item, score))

        pertinent = len(weighted)
        mean_similarity = sum(score for _, score in weighted) / pertinent if pertinent else 0.0
        favorable_weight = sum(score for item, score in weighted if item.outcome == "favorable")
        decided_weight = sum(score for item, score in weighted if item.outcome in {"favorable", "unfavorable"})
        raw_success = favorable_weight / decided_weight if decided_weight else None

        reasons: list[str] = []
        if pertinent < 3:
            reasons.append(
                f"Apenas {pertinent} de {total_documents} sentença(s) atingiram similaridade material (mínimo: 3)."
            )
        if raw_success is None:
            reasons.append(
                "As sentenças pertinentes não permitem identificar resultado unívoco para o evento de êxito."
            )

        if reasons:
            repetitividade = RepetitivenessAssessment(
                label="inconclusivo",
                probability=None,
                rationale=" ".join(reasons),
            )
            exito = SuccessAssessment(
                probability=None,
                rationale="Estimativa não publicada porque o gate de evidência mínima não foi atendido.",
            )
        else:
            label = "sim" if mean_similarity >= 0.80 else "nao" if mean_similarity <= 0.20 else "inconclusivo"
            repetitividade = RepetitivenessAssessment(
                label=label,
                probability=round(mean_similarity, 3),
                rationale=f"Média ponderada de similaridade em {pertinent} sentenças materialmente comparáveis.",
            )
            exito = SuccessAssessment(
                probability=round(raw_success, 3),
                rationale="Frequência ponderada por similaridade dos resultados favoráveis entre as sentenças pertinentes.",
            )

        summary = [
            f"{item.evidence_id}: similaridade {score:.0%}; resultado {item.outcome}."
            for item, score in weighted
        ] or ["Nenhuma sentença atingiu o limiar de similaridade material de 65%."]

        report = "\n".join([
            "# Relatório de Triagem Jurídica e Análise de Evidências",
            "",
            "## 1. Metodologia de Avaliação",
            "Cada sentença judicial foi avaliada sob 4 eixos ponderados:",
            "- **Fatos (35%)**: Coincidência fática e contexto material.",
            "- **Tese Jurídica (30%)**: Fundamentos legais e argumentos de direito.",
            "- **Pedido e Resultado (25%)**: Aderência das tutelas pleiteadas.",
            "- **Fase Processual (10%)**: Rito e grau de cognição.",
            "",
            "**Critérios de Publicação**: Limiar mínimo de similaridade de 65% e quórum de ao menos 3 sentenças pertinentes.",
            "",
            "## 2. Evidências Analisadas",
            *[f"- {line}" for line in summary],
            "",
            "## 3. Conclusão da Triagem",
            f"- **Repetitividade**: {repetitividade.label.upper()} — {repetitividade.rationale}",
            f"- **Estimativa de Êxito**: {f'{exito.probability:.1%}' if exito.probability is not None else 'N/A'} — {exito.rationale}",
            "",
            "## 4. Limites e Governança",
            *[f"- {reason}" for reason in reasons],
            "- **Atenção**: Esta análise constitui ferramenta de apoio à triagem e requer validação jurídica humana.",
        ])

        return DemandAssessment(
            repetitividade=repetitividade,
            exito=exito,
            evidence_ids=[item.evidence_id for item in comparisons],
            evidence_summary=summary,
            comparisons=comparisons,
            methodology="Rubrica determinística: fatos 35%, tese 30%, pedido/resultado 25%, fase 10%; limiar 65%; quórum mínimo de 3 sentenças.",
            report_markdown=report,
            limitations=reasons,
        )
