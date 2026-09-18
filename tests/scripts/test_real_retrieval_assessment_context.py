from apps.rag.state.models import AssessmentContext
from services.retrieval.retrieval_evaluator import RetrievalEvaluator
from services.retrieval.retrieval_service import RetrievalService


def test_real_retrieval_with_assessment_context():
    query = (
        "How does the organization restrict "
        "administrative access to critical systems?"
    )

    retriever = RetrievalService()
    evaluator = RetrievalEvaluator()

    print("\nSearching real database...")

    results = retriever.search(
        query,
        top_k=5,
    )

    assert results, "Expected real retrieval results from the database"

    print(f"Retrieved: {len(results)}")

    for index, result in enumerate(results, start=1):
        print(
            f"\nResult {index}"
            f"\n  Score: {result.score:.3f}"
            f"\n  Title: {result.document_title}"
            f"\n  Source: {result.source}"
            f"\n  Evidence: {result.evidence}"
        )

    us_context = AssessmentContext(
        jurisdiction="US",
    )

    india_context = AssessmentContext(
        jurisdiction="India",
    )

    us_evaluation = evaluator.evaluate(
        results,
        us_context,
    )

    india_evaluation = evaluator.evaluate(
        results,
        india_context,
    )

    print("\n--- US Assessment ---")
    print(f"Authority: {us_evaluation.authority}")
    print(f"Confidence: {us_evaluation.confidence}")
    print(f"Sufficient: {us_evaluation.sufficient}")

    print("\n--- India Assessment ---")
    print(f"Authority: {india_evaluation.authority}")
    print(f"Confidence: {india_evaluation.confidence}")
    print(f"Sufficient: {india_evaluation.sufficient}")

    assert us_evaluation.authority > 0
    assert india_evaluation.authority == 0.0


if __name__ == "__main__":
    tests = [
        test_real_retrieval_with_assessment_context,
    ]

    passed = 0

    for test in tests:
        try:
            test()
            print(f"\n[PASS] {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"\n[FAIL] {test.__name__}: {e}")

    print(
        f"\nReal retrieval assessment tests: "
        f"{passed}/{len(tests)} PASS"
    )

    if passed != len(tests):
        raise SystemExit(1)
