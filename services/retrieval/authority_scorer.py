from apps.rag.state.models import AssessmentContext, EvidenceScore
from services.retrieval.evidence_applicability import (
    EvidenceApplicabilityEvaluator,
)
from core.schemas.retrieval import RetrievalResult


class AuthorityScorer:
    AUTHORITY_SCORES = {
        "primary": 1.00,
        "official_guidance": 0.90,
        "certified_standard": 0.85,
        "organizational_policy": 0.75,
        "secondary": 0.50,
        "unverified": 0.20,
    }

    VERIFICATION_MULTIPLIERS = {
        "verified": 1.00,
        "partially_verified": 0.85,
        "unverified": 0.70,
    }

    def __init__(
        self,
        applicability_evaluator: EvidenceApplicabilityEvaluator | None = None,
    ):
        self.applicability_evaluator = (
            applicability_evaluator
            or EvidenceApplicabilityEvaluator()
        )

    def score(
        self,
        result: RetrievalResult,
        context: AssessmentContext | None = None,
    ) -> float:
        return self.score_details(result, context).combined

    def score_details(
        self,
        result: RetrievalResult,
        context: AssessmentContext | None = None,
    ) -> EvidenceScore:
        evidence = result.evidence

        if evidence is None:
            authority = 0.70
            applicability = 0.0 if context else 1.0

            return EvidenceScore(
                authority=authority,
                applicability=applicability,
                combined=round(authority * applicability, 3),
            )

        authority_base = self.AUTHORITY_SCORES.get(
            evidence.authority_level.value,
            0.50,
        )

        verification_multiplier = self.VERIFICATION_MULTIPLIERS.get(
            evidence.verification_status.value,
            0.70,
        )

        authority = round(
            authority_base * verification_multiplier,
            3,
        )

        applicability = 1.0

        if context:
            applicability = (
                self.applicability_evaluator.evaluate(
                    result,
                    context,
                )
            )

        return EvidenceScore(
            authority=authority,
            applicability=applicability,
            combined=round(
                authority * applicability,
                3,
            ),
        )
