from datetime import date

from core.schemas.retrieval import RetrievalResult
from apps.rag.state.models import AssessmentContext


class EvidenceApplicabilityEvaluator:
    def evaluate(
        self,
        result: RetrievalResult,
        context: AssessmentContext,
    ) -> float:
        evidence = result.evidence

        if evidence is None:
            return 0.0

        scores = []

        if context.jurisdiction:
            scores.append(
                self._evaluate_jurisdiction(
                    evidence.jurisdiction,
                    context.jurisdiction,
                )
            )

        if context.assessment_date:
            scores.append(
                self._evaluate_effective_date(
                    evidence.effective_date,
                    context.assessment_date,
                )
            )

            scores.append(
                self._evaluate_expiration_date(
                    evidence.expiration_date,
                    context.assessment_date,
                )
            )

        if not scores:
            return 1.0

        # Hard applicability failures must dominate.
        if any(score == 0.0 for score in scores):
            return 0.0

        return round(sum(scores) / len(scores), 3)

    def _evaluate_jurisdiction(
        self,
        evidence_jurisdiction: str | None,
        assessment_jurisdiction: str,
    ) -> float:
        if not evidence_jurisdiction:
            return 0.5

        if evidence_jurisdiction.upper() == assessment_jurisdiction.upper():
            return 1.0

        return 0.0

    def _evaluate_effective_date(
        self,
        effective_date: date | None,
        assessment_date: date,
    ) -> float:
        if effective_date is None:
            return 0.5

        return 1.0 if effective_date <= assessment_date else 0.0

    def _evaluate_expiration_date(
        self,
        expiration_date: date | None,
        assessment_date: date,
    ) -> float:
        if expiration_date is None:
            return 1.0

        return 1.0 if assessment_date <= expiration_date else 0.0
