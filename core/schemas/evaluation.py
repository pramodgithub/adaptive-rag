from pydantic import BaseModel


class AnswerEvaluation(BaseModel):
    grounded: bool
    complete: bool
    confidence: float
    should_retry: bool
    reason: str
