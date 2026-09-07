import json
from pathlib import Path

from services.retrieval.retrieval_service import RetrievalService
from services.retrieval.retrieval_evaluator import RetrievalEvaluator


TEST_CASES_PATH = Path(__file__).parent / "data" / "retrieval_test_cases.json"


def load_test_cases():
    with TEST_CASES_PATH.open("r", encoding="utf-8") as file:
        dataset = json.load(file)

    return dataset["cases"], dataset.get("top_k", 5)


def main():
    test_cases, top_k = load_test_cases()

    retrieval_service = RetrievalService()
    evaluator = RetrievalEvaluator()

    passed = 0

    print("\n" + "=" * 70)
    print("Retrieval Evaluation Test")
    print("=" * 70)

    for test_case in test_cases:
        results = retrieval_service.search(
            test_case["query"],
            top_k=top_k
        )

        evaluation = evaluator.evaluate(results=results)

        status = "PASS" if evaluation.sufficient else "FAIL"

        if evaluation.sufficient:
            passed += 1

        print(f"\n[{status}] {test_case['id']}")
        print(f"Query: {test_case['query']}")
        print(f"Relevance:    {evaluation.relevance:.3f}")
        print(f"Coverage:     {evaluation.coverage:.3f}")
        print(f"Authority:    {evaluation.authority:.3f}")
        print(f"Completeness: {evaluation.completeness:.3f}")
        print(f"Consistency:  {evaluation.consistency:.3f}")
        print(f"Confidence:   {evaluation.confidence:.3f}")
        print(f"Sufficient:   {evaluation.sufficient}")
        print(f"Reason:       {evaluation.reason}")
        print("Top Score:", results[0].score)
        print("Source:", results[0].source)
        print("Evidence:", results[0].evidence)

        if evaluation.missing_evidence:
            print("Missing evidence:")
            for evidence in evaluation.missing_evidence:
                print(f"  - {evidence}")

    total = len(test_cases)

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Queries:  {total}")
    print(f"Passed:   {passed}")
    print(f"Failed:   {total - passed}")
    print(
        f"Pass Rate: {(passed / total):.2%}" if total else "Pass Rate: 0.00%")


if __name__ == "__main__":
    main()
