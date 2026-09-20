from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field, HttpUrl


class StructuredDemand(BaseModel):
    summary: str
    legal_theses: list[str] = Field(default_factory=list)
    requested_outcomes: list[str] = Field(default_factory=list)
    relevant_facts: list[str] = Field(default_factory=list)
    target_judge: str | None = None
    target_court: str | None = None


class ResearchPlan(BaseModel):
    query: str
    judge: str | None = None
    court: str | None = None
    similarity_criteria: list[str] = Field(default_factory=list)
    document_limit: int = Field(default=10, ge=1, le=10)


class DownloadedDocument(BaseModel):
    case_id: str
    title: str
    source_url: str
    local_path: str
    sha256: str
    text_excerpt: str
    judge: str | None = None
    court: str | None = None
    similarity_reason: str
    similarity_score: float = Field(ge=0, le=1)


class AuditEvent(BaseModel):
    node: str
    message: str


class RepetitivenessAssessment(BaseModel):
    label: Literal["sim", "nao", "inconclusivo"]
    probability: float | None = Field(default=None, ge=0, le=1)
    rationale: str


class SuccessAssessment(BaseModel):
    probability: float | None = Field(default=None, ge=0, le=1)
    rationale: str


class EvidenceComparison(BaseModel):
    """Leitura de uma sentença em relação à demanda, nunca um veredito isolado."""

    evidence_id: str
    factual_match: float = Field(ge=0, le=1)
    legal_match: float = Field(ge=0, le=1)
    requested_outcome_match: float = Field(ge=0, le=1)
    procedural_match: float = Field(ge=0, le=1)
    material_differences: list[str] = Field(default_factory=list)
    outcome: Literal["favorable", "unfavorable", "mixed", "unknown"]
    outcome_basis: str
    excerpts: list[str] = Field(default_factory=list, max_length=3)


class DebateTurn(BaseModel):
    role: Literal["advocate", "risk_auditor", "synthesis"]
    speaker_name: str
    argument: str


class DemandAssessment(BaseModel):
    """Saída experimental; requer revisão jurídica humana."""

    repetitividade: RepetitivenessAssessment
    exito: SuccessAssessment
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)
    comparisons: list[EvidenceComparison] = Field(default_factory=list)
    debate: list[DebateTurn] = Field(default_factory=list)
    methodology: str = ""
    report_markdown: str = ""
    limitations: list[str] = Field(default_factory=list)
    review_required: Literal[True] = True
    calibration_status: Literal["not_validated"] = "not_validated"


class ResearchState(TypedDict, total=False):
    run_id: str
    original_demand: str
    source_pdf: str | None
    source_text_file: str | None
    drive_artifact: dict
    document_limit: int
    source_document: dict
    structured_demand: dict
    research_plan: dict
    documents: list[dict]
    assessment: dict
    errors: list[str]
    audit: list[dict]
    status: Literal["running", "completed", "failed"]
