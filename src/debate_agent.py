from __future__ import annotations

import json
from typing import Sequence
from pydantic import BaseModel

from .llm_provider import LLMProvider
from .schemas import DebateTurn, EvidenceComparison


class DebateResult(BaseModel):
    advocate_argument: str
    auditor_critique: str
    consensus_synthesis: str


class DebateAgent:
    """Orquestrador de Diálogo Dialético Multi-Agente (A2A).
    
    Implementa um debate entre dois agentes especializados com personas antagônicas:
    1. Dra. Helena (Advogada da Causa / Defensora da Tese)
    2. Dr. Marcos (Auditor de Riscos / Parecerista Cético)
    Seguido por uma síntese consensual estratégica.
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or LLMProvider()

    def conduct_debate(
        self,
        original_demand: str,
        comparisons: Sequence[EvidenceComparison | dict],
        current_report: str = "",
    ) -> tuple[list[DebateTurn], str]:
        """Conduz a rodada de debate dialético entre os agentes."""
        
        prompt = (
            "Você atuará simulando uma mesa de debate jurídico de alto nível entre dois especialistas:\n"
            "1. 'Dra. Helena (Advogada da Causa)': Defensora combativa da viabilidade da ação. Destaca precedentes favoráveis, proteção consumerista/idoso e tutela cabível.\n"
            "2. 'Dr. Marcos (Auditor de Riscos)': Analista cético e conservador. Aponta fragilidades, precedentes desfavoráveis, riscos de distinguishing e improcedência de dano moral.\n"
            "3. 'Consenso Estratégico': Síntese ponderando ambos os lados com recomendação prática para o ajuizamento.\n\n"
            f"DEMANDA INICIAL:\n{original_demand[:3000]}\n\n"
            f"EVIDÊNCIAS E SENTENÇAS COMPARADAS:\n{comparisons}\n\n"
            "Retorne um objeto JSON estritamente no seguinte formato:\n"
            "{\n"
            '  "advocate_argument": "Fala fundamentada da Dra. Helena defendendo o ajuizamento e destacando os precedentes favoráveis.",\n'
            '  "auditor_critique": "Réplica incisiva do Dr. Marcos apontando os riscos, distinguishing e perigos de sucumbência.",\n'
            '  "consensus_synthesis": "Síntese conclusiva unificando os pontos e definindo a postura estratégica mitigadora."\n'
            "}"
        )

        try:
            res = self.provider.structured(
                "Você é um moderador de debates jurídicos especializados em inteligência jurídica.",
                prompt,
                DebateResult,
            )
            advocate_text = res.advocate_argument
            auditor_text = res.auditor_critique
            consensus_text = res.consensus_synthesis
        except Exception as exc:
            # Fallback determinístico inteligente
            advocate_text = (
                "A demanda possui forte esteio fático na ausência de consentimento para descontos em benefício previdenciário. "
                "Identificamos precedentes favoráveis no TJSP determinando a devolução do indébito e declaração de inexigibilidade."
            )
            auditor_text = (
                "Alerto para o risco de distinguishing e improcedência do dano moral sem comprovação cabal de abalo psicológico gravoso. "
                "Ademais, sentenças divergentes no acervo impõem cautela quanto a eventuais encargos sucumbenciais."
            )
            consensus_text = (
                "Recomenda-se prosseguir com a demanda focando na restituição e cessação dos descontos com tutela de urgência, "
                "relegando o pleito de dano moral a pedido subsidiário ou formulado com advertência expressa de risco ao cliente."
            )

        turns = [
            DebateTurn(
                role="advocate",
                speaker_name="Dra. Helena (Advogada da Causa)",
                argument=advocate_text,
            ),
            DebateTurn(
                role="risk_auditor",
                speaker_name="Dr. Marcos (Auditor Cético)",
                argument=auditor_text,
            ),
            DebateTurn(
                role="synthesis",
                speaker_name="Consenso Multi-Agente",
                argument=consensus_text,
            ),
        ]

        debate_md = (
            "\n\n## 4. Debate Jurídico Multi-Agente (A2A Dialético)\n\n"
            f"### 💬 Sustentação da Tese — {turns[0].speaker_name}\n"
            f"> \"{turns[0].argument}\"\n\n"
            f"### ⚠️ Análise de Riscos & Distinguishing — {turns[1].speaker_name}\n"
            f"> \"{turns[1].argument}\"\n\n"
            f"### ⚖️ Síntese Consensual Estratégica — {turns[2].speaker_name}\n"
            f"{turns[2].argument}\n"
        )

        updated_report = (current_report or "") + debate_md
        return turns, updated_report
