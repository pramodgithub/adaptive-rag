from uuid import UUID

from pydantic import BaseModel


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


class RetrievalEvaluation(BaseModel):
    confidence: float
    should_retry: bool
    reason: str


class RetrievalJudgeEvaluation(BaseModel):

    relevant: bool
    coverage: float
    confidence: float
    reason: str
