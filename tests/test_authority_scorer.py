from datetime import date

from apps.rag.state.models import AssessmentContext
from core.schemas.evidence import EvidenceMetadata
from core.schemas.retrieval import RetrievalResult
from services.retrieval.authority_scorer import AuthorityScorer
from enums.authority_levels import AuthorityLevel, VerificationStatus


def build_result(evidence=None):
    return RetrievalResult(
        chunk_id="00000000-0000-0000-0000-000000000001",
        document_id="00000000-0000-0000-0000-000000000002",
        document_version_id="00000000-0000-0000-0000-000000000003",
        chunk_index=0,
        page_number=1,
        document_title="Test Document",
        text="Test evidence",
        score=0.8,
        source="vector",
        evidence=evidence,
    )


def test_missing_metadata_uses_legacy_score():
    scorer = AuthorityScorer()

    assert scorer.score(build_result()) == 0.70


def test_primary_verified_source():
    scorer = AuthorityScorer()

    evidence = EvidenceMetadata(
        source_type="regulation",
        issuer="Government Authority",
        jurisdiction="India",
        authority_level=AuthorityLevel.PRIMARY,
        verification_status=VerificationStatus.VERIFIED,
    )

    assert scorer.score(build_result(evidence)) == 1.00


def test_secondary_verified_source():
    scorer = AuthorityScorer()

    evidence = EvidenceMetadata(
        source_type="article",
        issuer="Industry Organization",
        jurisdiction="India",
        authority_level="secondary",
        verification_status="verified",
    )

    assert scorer.score(build_result(evidence)) == 0.50


def test_primary_unverified_source():
    scorer = AuthorityScorer()

    evidence = EvidenceMetadata(
        source_type="regulation",
        issuer="Government Authority",
        jurisdiction="India",
        authority_level="primary",
        verification_status="unverified",
    )

    assert scorer.score(build_result(evidence)) == 0.70


def test_authoritative_and_applicable():
    scorer = AuthorityScorer()

    evidence = EvidenceMetadata(
        source_type="regulation",
        issuer="Government Authority",
        jurisdiction="US",
        authority_level=AuthorityLevel.PRIMARY,
        effective_date=date(2025, 1, 1),
        verification_status=VerificationStatus.VERIFIED,
    )

    result = build_result(evidence)

    context = AssessmentContext(
        jurisdiction="US",
        assessment_date=date(2026, 9, 3),
    )

    score = scorer.score_details(result, context)

    assert score.authority == 1.0
    assert score.applicability == 1.0
    assert score.combined == 1.0


def test_authoritative_but_wrong_jurisdiction():
    scorer = AuthorityScorer()

    evidence = EvidenceMetadata(
        source_type="regulation",
        issuer="Government Authority",
        jurisdiction="US",
        authority_level=AuthorityLevel.PRIMARY,
        verification_status=VerificationStatus.VERIFIED,
    )

    result = build_result(evidence)

    context = AssessmentContext(
        jurisdiction="IN",
        assessment_date=date(2026, 9, 3),
    )

    score = scorer.score_details(result, context)

    assert score.authority == 1.0
    assert score.applicability == 0.0
    assert score.combined == 0.0


def test_authoritative_but_expired():
    scorer = AuthorityScorer()

    evidence = EvidenceMetadata(
        source_type="regulation",
        issuer="Government Authority",
        jurisdiction="US",
        authority_level=AuthorityLevel.PRIMARY,
        expiration_date=date(2025, 12, 31),
        verification_status=VerificationStatus.VERIFIED,
    )

    result = build_result(evidence)

    context = AssessmentContext(
        jurisdiction="US",
        assessment_date=date(2026, 9, 3),
    )

    score = scorer.score_details(result, context)

    assert score.authority == 1.0
    assert score.applicability == 0.0
    assert score.combined == 0.0


def test_missing_metadata_with_context():
    scorer = AuthorityScorer()

    result = build_result()

    context = AssessmentContext(
        jurisdiction="US",
        assessment_date=date(2026, 9, 3),
    )

    score = scorer.score_details(result, context)

    assert score.authority == 0.70
    assert score.applicability == 0.0
    assert score.combined == 0.0


if __name__ == "__main__":
    tests = [
        test_missing_metadata_uses_legacy_score,
        test_primary_verified_source,
        test_secondary_verified_source,
        test_primary_unverified_source,
        test_authoritative_and_applicable,
        test_authoritative_but_wrong_jurisdiction,
        test_authoritative_but_expired,
        test_missing_metadata_with_context,
    ]

    passed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test.__name__}: {exc}")

    print(f"\nAuthority scorer tests: {passed}/{len(tests)} PASS")
