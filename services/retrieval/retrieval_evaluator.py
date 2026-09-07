import mlflow
from mlflow import trace
from apps.rag.state.models import AssessmentContext, RetrievalEvaluation, RetrievalEvaluationPolicy
from core.schemas.retrieval import RetrievalResult
from services.retrieval.authority_scorer import AuthorityScorer


class RetrievalEvaluator:
    def __init__(
        self,
        policy: RetrievalEvaluationPolicy | None = None,
        authority_scorer: AuthorityScorer | None = None,
    ):
        self.policy = policy or RetrievalEvaluationPolicy()
        self.authority_scorer = authority_scorer or AuthorityScorer()

    @trace
    def evaluate(
        self,
        results: list[RetrievalResult],
        context: AssessmentContext | None = None,
    ) -> RetrievalEvaluation:

        if not results:
            mlflow.log_metric("retrieval_confidence", 0)

            return RetrievalEvaluation(
                relevance=0,
                coverage=0,
                authority=0,
                completeness=0,
                consistency=0,
                confidence=0,
                sufficient=False,
                missing_evidence=["No retrieval results found"],
                reason="No evidence was retrieved.",
            )

        relevance = self._calculate_relevance(results)
        coverage = self._calculate_coverage(results)
        authority = self._calculate_authority(results, context)
        completeness = self._calculate_completeness(results)
        consistency = self._calculate_consistency(results)

        confidence = self._calculate_confidence(
            relevance=relevance,
            coverage=coverage,
            authority=authority,
            completeness=completeness,
            consistency=consistency,
        )

        sufficient = self._is_sufficient(
            relevance=relevance,
            coverage=coverage,
            authority=authority,
            completeness=completeness,
            consistency=consistency,
            confidence=confidence,
        )

        missing_evidence = self._identify_missing_evidence(
            relevance=relevance,
            coverage=coverage,
            authority=authority,
            completeness=completeness,
            consistency=consistency,
        )

        reason = self._build_reason(
            sufficient,
            relevance,
            coverage,
            completeness,
            confidence,
        )

        mlflow.log_metric("retrieval_relevance", relevance)
        mlflow.log_metric("retrieval_coverage", coverage)
        mlflow.log_metric("retrieval_authority", authority)
        mlflow.log_metric("retrieval_completeness", completeness)
        mlflow.log_metric("retrieval_consistency", consistency)
        mlflow.log_metric("retrieval_confidence", confidence)

        return RetrievalEvaluation(
            relevance=relevance,
            coverage=coverage,
            authority=authority,
            completeness=completeness,
            consistency=consistency,
            confidence=confidence,
            sufficient=sufficient,
            missing_evidence=missing_evidence,
            reason=reason,
        )

    def _calculate_relevance(
        self,
        results: list[RetrievalResult],
    ) -> float:
        return round(
            sum(result.score for result in results) / len(results),
            3,
        )

    # EvidenceSource
    # │
    # ├── source_type
    # ├── authority_level
    # ├── issuer
    # ├── jurisdiction
    # ├── publication_date
    # ├── effective_date
    # ├── expiration_date
    # └── verification_status
    # will drive authority.
    # This is critical for multi-country compliance.

    def _calculate_authority(
        self,
        results: list[RetrievalResult],
        context: AssessmentContext | None = None,
    ):
        if not results:
            return 0.0

        scores = [
            self.authority_scorer.score(
                result,
                context,
            )
            for result in results
        ]

        return round(sum(scores) / len(scores), 3)

    def _calculate_coverage(
        self,
        results: list[RetrievalResult],
    ) -> float:
        if not results:
            return 0.0

        unique_chunks = {
            result.chunk_id
            for result in results
        }

        if not unique_chunks:
            return 0.0

        return round(
            min(len(unique_chunks) / 3, 1.0),
            3,
        )

    def _calculate_completeness(
        self,
        results: list[RetrievalResult],
    ) -> float:
        if not results:
            return 0.0

        top_score = results[0].score
        result_count = len(results)

        score_component = min(top_score / 0.75, 1.0)
        count_component = min(result_count / 3, 1.0)

        return round(
            (score_component * 0.6) + (count_component * 0.4),
            3,
        )

    def _calculate_consistency(
        self,
        results: list[RetrievalResult],
    ) -> float:
        return 1.0

    def _calculate_confidence(
        self,
        relevance: float,
        coverage: float,
        authority: float,
        completeness: float,
        consistency: float,
    ) -> float:
        confidence = (
            relevance * 0.30
            + coverage * 0.20
            + authority * 0.15
            + completeness * 0.20
            + consistency * 0.15
        )

        return round(confidence, 3)

    def _is_sufficient(
        self,
        relevance: float,
        coverage: float,
        authority: float,
        completeness: float,
        consistency: float,
        confidence: float,
    ) -> bool:
        policy = self.policy

        return all(
            [
                relevance >= policy.min_relevance,
                coverage >= policy.min_coverage,
                authority >= policy.min_authority,
                completeness >= policy.min_completeness,
                consistency >= policy.min_consistency,
                confidence >= policy.min_confidence,
            ]
        )

    def _identify_missing_evidence(
        self,
        relevance: float,
        coverage: float,
        authority: float,
        completeness: float,
        consistency: float,
    ) -> list[str]:
        policy = self.policy
        missing = []

        if relevance < policy.min_relevance:
            missing.append("Relevant evidence")

        if coverage < policy.min_coverage:
            missing.append("Evidence covering the requested requirement")

        if authority < policy.min_authority:
            missing.append("Authoritative evidence")

        if completeness < policy.min_completeness:
            missing.append("Complete evidence")

        if consistency < policy.min_consistency:
            missing.append("Consistent evidence")

        return missing

    def _build_reason(
        self,
        sufficient: bool,
        relevance: float,
        coverage: float,
        completeness: float,
        confidence: float,
    ) -> str:
        if sufficient:
            return (
                f"Retrieval is sufficient with "
                f"relevance={relevance:.2f}, "
                f"coverage={coverage:.2f}, "
                f"completeness={completeness:.2f}, "
                f"and confidence={confidence:.2f}."
            )

        return (
            f"Retrieval is insufficient with "
            f"relevance={relevance:.2f}, "
            f"coverage={coverage:.2f}, "
            f"completeness={completeness:.2f}, "
            f"and confidence={confidence:.2f}."
        )
