from pydantic import BaseModel


class RetrievalResult(BaseModel):
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
