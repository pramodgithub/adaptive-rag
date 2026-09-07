from datetime import date
from core.schemas.retrieval import RetrievalResult
from pydantic import BaseModel, Field


class RetrievalEvaluation(BaseModel):
    relevance: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    authority: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    consistency: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    sufficient: bool
    should_retry: bool = False
    missing_evidence: list[str] = Field(default_factory=list)
    reason: str


class RetrievalEvaluationRequest(BaseModel):
    query: str
    results: list[RetrievalResult]


class RetrievalEvaluationPolicy(BaseModel):
    min_relevance: float = Field(default=0.65, ge=0.0, le=1.0)
    min_coverage: float = Field(default=0.70, ge=0.0, le=1.0)
    min_authority: float = Field(default=0.70, ge=0.0, le=1.0)
    min_completeness: float = Field(default=0.70, ge=0.0, le=1.0)
    min_consistency: float = Field(default=0.70, ge=0.0, le=1.0)
    min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)


class AssessmentContext(BaseModel):
    jurisdiction: str | None = None
    sector: str | None = None
    regulation: str | None = None
    assessment_date: date | None = None


class EvidenceScore(BaseModel):
    authority: float
    applicability: float
    combined: float
