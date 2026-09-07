from datetime import date

from apps.rag.state.models import AssessmentContext
from services.retrieval.evidence_applicability import (
    EvidenceApplicabilityEvaluator,
)
from core.schemas.evidence import (
    AuthorityLevel,
    EvidenceMetadata,
    VerificationStatus,
)
from core.schemas.retrieval import RetrievalResult


def build_result(
    *,
    jurisdiction: str | None = "US",
    effective_date: date | None = date(2025, 1, 1),
    expiration_date: date | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id="00000000-0000-0000-0000-000000000001",
        document_id="00000000-0000-0000-0000-000000000002",
        document_version_id="00000000-0000-0000-0000-000000000003",
        chunk_index=0,
        page_number=1,
        document_title="Test Document",
        text="Test evidence",
        score=0.9,
        source="vector",
        evidence=EvidenceMetadata(
            source_type="regulation",
            issuer="Test Authority",
            jurisdiction=jurisdiction,
            authority_level=AuthorityLevel.PRIMARY,
            publication_date=date(2024, 1, 1),
            effective_date=effective_date,
            expiration_date=expiration_date,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )


def test_matching_jurisdiction():
    evaluator = EvidenceApplicabilityEvaluator()

    result = build_result(jurisdiction="US")

    context = AssessmentContext(
        jurisdiction="US",
        assessment_date=date(2026, 9, 3),
    )

    score = evaluator.evaluate(result, context)

    assert score == 1.0


def test_mismatched_jurisdiction():
    evaluator = EvidenceApplicabilityEvaluator()

    result = build_result(jurisdiction="US")

    context = AssessmentContext(
        jurisdiction="IN",
        assessment_date=date(2026, 9, 3),
    )

    score = evaluator.evaluate(result, context)

    assert score == 0.0


def test_missing_jurisdiction():
    evaluator = EvidenceApplicabilityEvaluator()

    result = build_result(jurisdiction=None)

    context = AssessmentContext(
        jurisdiction="US",
        assessment_date=date(2026, 9, 3),
    )

    score = evaluator.evaluate(result, context)

    assert score == 0.833


def test_not_yet_effective():
    evaluator = EvidenceApplicabilityEvaluator()

    result = build_result(
        effective_date=date(2027, 1, 1),
    )

    context = AssessmentContext(
        jurisdiction="US",
        assessment_date=date(2026, 9, 3),
    )

    score = evaluator.evaluate(result, context)

    assert score == 0.0


def test_expired():
    evaluator = EvidenceApplicabilityEvaluator()

    result = build_result(
        expiration_date=date(2025, 12, 31),
    )

    context = AssessmentContext(
        jurisdiction="US",
        assessment_date=date(2026, 9, 3),
    )

    score = evaluator.evaluate(result, context)

    assert score == 0.0


def test_missing_evidence():
    evaluator = EvidenceApplicabilityEvaluator()

    result = build_result()
    result.evidence = None

    context = AssessmentContext(
        jurisdiction="US",
        assessment_date=date(2026, 9, 3),
    )

    score = evaluator.evaluate(result, context)

    assert score == 0.0


def test_no_applicability_constraints():
    evaluator = EvidenceApplicabilityEvaluator()

    result = build_result()

    context = AssessmentContext()

    score = evaluator.evaluate(result, context)

    assert score == 1.0


print("Evidence applicability tests loaded.")


if __name__ == "__main__":
    tests = [
        test_matching_jurisdiction,
        test_mismatched_jurisdiction,
        test_missing_jurisdiction,
        test_not_yet_effective,
        test_expired,
        test_missing_evidence,
        test_no_applicability_constraints,
    ]

    passed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test.__name__}: {exc}")

    print(f"\nEvidence applicability tests: {passed}/{len(tests)} PASS")
