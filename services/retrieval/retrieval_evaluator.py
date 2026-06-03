import mlflow
from mlflow import trace

from core.schemas.retrieval import RetrievalEvaluation
from core.schemas.retrieval import RetrievalResult


class RetrievalEvaluator:

    RETRY_THRESHOLD = 0.40

    @trace
    def evaluate(
        self,
        results: list[RetrievalResult]
    ) -> RetrievalEvaluation:

        if not results:
            mlflow.log_metric("retrieval_confidence", 0)
            return RetrievalEvaluation(
                confidence=0,
                should_retry=True,
                reason="No results found"
            )

        scores = [r.score for r in results]

        top_score = max(scores)
        average_score = sum(scores) / len(scores)

        confidence = round(
            (top_score + average_score) / 2,
            2
        )

        should_retry = (
            confidence < self.RETRY_THRESHOLD
        )
        mlflow.log_metric("retrieval_confidence", confidence)
        reason = (
            "Low retrieval confidence"
            if should_retry
            else "Retrieval acceptable"
        )

        return RetrievalEvaluation(
            confidence=confidence,
            should_retry=should_retry,
            reason=reason
        )
