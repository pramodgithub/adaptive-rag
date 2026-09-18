from apps.rag.state.models import AssessmentContext
from services.retrieval.rag_service import RAGService


def test_real_rag_with_matching_jurisdiction():
    service = RAGService()

    result = service.ask(
        "How does the organization restrict administrative access to critical systems?",
        AssessmentContext(
            jurisdiction="US"
        ),
    )

    retrieval = result["retrieval_evaluation"]

    print("\n--- Matching jurisdiction ---")
    print(f"Authority: {retrieval.authority}")
    print(f"Confidence: {retrieval.confidence}")
    print(f"Sufficient: {retrieval.sufficient}")
    print(f"Retrieved: {len(result['retrieved'])}")

    assert result["retrieved"]
    assert retrieval.authority > 0


def test_real_rag_with_wrong_jurisdiction():
    service = RAGService()

    result = service.ask(
        "How does the organization restrict administrative access to critical systems?",
        AssessmentContext(
            jurisdiction="India"
        ),
    )

    retrieval = result["retrieval_evaluation"]

    print("\n--- Wrong jurisdiction ---")
    print(f"Authority: {retrieval.authority}")
    print(f"Confidence: {retrieval.confidence}")
    print(f"Sufficient: {retrieval.sufficient}")
    print(f"Retrieved: {len(result['retrieved'])}")

    assert result["retrieved"]
    assert retrieval.authority == 0.0


if __name__ == "__main__":
    tests = [
        test_real_rag_with_matching_jurisdiction,
        test_real_rag_with_wrong_jurisdiction,
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
        f"\nRAG assessment context integration tests: "
        f"{passed}/{len(tests)} PASS"
    )

    if passed != len(tests):
        raise SystemExit(1)
