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


class ResearchState(TypedDict, total=False):
    run_id: str
    original_demand: str
    source_pdf: str | None
    source_text_file: str | None
    document_limit: int
    source_document: dict
    structured_demand: dict
    research_plan: dict
    documents: list[dict]
    errors: list[str]
    audit: list[dict]
    status: Literal["running", "completed", "failed"]
