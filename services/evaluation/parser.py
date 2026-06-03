import json

from core.schemas.retrieval import RetrievalJudgeEvaluation


class EvaluationParser:

    @staticmethod
    def parse(response: str):

        try:

            return json.loads(
                response
            )

        except:

            return {
                "relevant": False,
                "confidence": 0,
                "reason": "Invalid response"
            }

    @staticmethod
    def parsejudge(
        response: str
    ) -> RetrievalJudgeEvaluation:

        try:

            data = json.loads(
                response
            )

            return RetrievalJudgeEvaluation(
                relevant=data["relevant"],
                coverage=data["coverage"],
                confidence=data["confidence"],
                reason=data["reason"]
            )

        except Exception:

            return RetrievalJudgeEvaluation(
                relevant=False,
                coverage=0,
                confidence=0,
                reason="Invalid response"
            )
