from uuid import UUID

from pydantic import BaseModel, Field

from core.schemas.evidence import EvidenceMetadata
from enums.judge_status import JudgeStatus


class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_version_id: UUID
    chunk_index: int
    page_number: int | None
    document_title: str
    text: str
    score: float
    source: str
    evidence: EvidenceMetadata | None = None


class RetrievalEvaluation(BaseModel):
    confidence: float
    should_retry: bool
    reason: str


class RetrievalJudgeResult(BaseModel):
   # status: JudgeStatus

    relevant: bool
    coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)

    missing_evidence: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)

    sufficient: bool
    reason: str
