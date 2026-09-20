"""Núcleo do sistema de pesquisa e análise jurídica — 3 Agentes Especialistas."""

from .analysis_agent import AnalysisAgent
from .orchestrator import OrchestratorAgent
from .research_agent import ResearchAgent
from .schemas import DemandAssessment, EvidenceComparison, ResearchPlan, ResearchState, StructuredDemand

__all__ = [
    "OrchestratorAgent",
    "ResearchAgent",
    "AnalysisAgent",
    "ResearchState",
    "StructuredDemand",
    "ResearchPlan",
    "DemandAssessment",
    "EvidenceComparison",
]
