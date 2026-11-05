from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Language = Literal["uz", "ru"]


class EvidenceItem(BaseModel):
    label: str
    value: str


class Verification(BaseModel):
    passed: bool
    method: str
    notes: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    language: Language | None = None


class AskResponse(BaseModel):
    question: str
    language: Language
    found: bool
    answer: str
    confidence: float
    intent: str
    reasoning_summary: str
    sql: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    execution_ms: float
    verification: Verification
    cached: bool = False


class HealthResponse(BaseModel):
    status: str
    database_ready: bool
    llm_sql_enabled: bool
    stats: dict[str, Any] = Field(default_factory=dict)


class StatsResponse(BaseModel):
    stats: dict[str, Any]
    suggested_questions: dict[str, list[str]]
