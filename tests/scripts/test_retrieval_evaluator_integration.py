from apps.rag.state.models import AssessmentContext
from core.schemas.evidence import EvidenceMetadata
from core.schemas.retrieval import RetrievalResult
from enums.authority_levels import AuthorityLevel, VerificationStatus
from graph.nodes import evaluate_retrieval_node


def build_result(jurisdiction="US"):
    evidence = EvidenceMetadata(
        source_type="regulation",
        issuer="Government Authority",
        jurisdiction=jurisdiction,
        authority_level=AuthorityLevel.PRIMARY,
        verification_status=VerificationStatus.VERIFIED,
    )

    return RetrievalResult(
        chunk_id="00000000-0000-0000-0000-000000000001",
        document_id="00000000-0000-0000-0000-000000000002",
        document_version_id="00000000-0000-0000-0000-000000000003",
        chunk_index=0,
        page_number=1,
        document_title="Test Regulation",
        text="Access management controls must be implemented.",
        score=0.8,
        source="vector",
        evidence=evidence,
    )


def build_state(result, jurisdiction):
    return {
        "query": "What are the access management requirements?",
        "retrieved": [result],
        "assessment_context": AssessmentContext(
            jurisdiction=jurisdiction
        ),
        "retry_count": 0,
        "node_metrics": {},
    }


def test_evaluator_accepts_matching_jurisdiction():
    result = build_result("US")
    state = build_state(result, "US")

    output = evaluate_retrieval_node(state)

    evaluation = output["retrieval"]

    assert evaluation.authority == 1.0


def test_evaluator_rejects_wrong_jurisdiction():
    result = build_result("US")
    state = build_state(result, "India")

    output = evaluate_retrieval_node(state)

    evaluation = output["retrieval"]

    assert evaluation.authority == 0.0


def test_evaluator_without_context_preserves_legacy_behavior():
    result = build_result("US")

    state = {
        "query": "What are the access management requirements?",
        "retrieved": [result],
        "assessment_context": None,
        "retry_count": 0,
        "node_metrics": {},
    }

    output = evaluate_retrieval_node(state)

    evaluation = output["retrieval"]

    assert evaluation.authority == 1.0


if __name__ == "__main__":
    tests = [
        test_evaluator_accepts_matching_jurisdiction,
        test_evaluator_rejects_wrong_jurisdiction,
        test_evaluator_without_context_preserves_legacy_behavior,
    ]

    passed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")

    print(
        f"\nRetrieval evaluator integration tests: {passed}/{len(tests)} PASS")

    if passed != len(tests):
        raise SystemExit(1)
