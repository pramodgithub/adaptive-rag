import json

from pydantic import ValidationError

from core.schemas.retrieval import RetrievalJudgeResult


class RetrievalJudgeParser:

    @staticmethod
    def parse(response: str) -> RetrievalJudgeResult:
        try:
            data = json.loads(response)

            return RetrievalJudgeResult.model_validate(data)

        except (json.JSONDecodeError, ValidationError, TypeError):
            return RetrievalJudgeResult(
                relevant=False,
                coverage=0.0,
                confidence=0.0,
                missing_evidence=[],
                contradictions=[],
                sufficient=False,
                reason="Invalid retrieval judge response.",
            )
