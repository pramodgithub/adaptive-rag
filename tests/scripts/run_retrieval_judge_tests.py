import traceback

from test_retrieval_judge import (
    test_sufficient_evidence,
    test_relevant_but_incomplete_evidence,
    test_missing_evidence,
    test_contradictory_evidence,
    test_irrelevant_evidence,
    test_malformed_json,
    test_invalid_field_values,
    test_missing_required_field,
    test_llm_failure_is_propagated,
)


TESTS = [
    test_sufficient_evidence,
    test_relevant_but_incomplete_evidence,
    test_missing_evidence,
    test_contradictory_evidence,
    test_irrelevant_evidence,
    test_malformed_json,
    test_invalid_field_values,
    test_missing_required_field,
    test_llm_failure_is_propagated,
]


def main():
    passed = 0
    failed = 0

    print("=" * 60)
    print("Retrieval Judge Tests")
    print("=" * 60)

    for test in TESTS:
        try:
            test()
            passed += 1
            print(f"[PASS] {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {test.__name__}")
            print(f"       {exc}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{len(TESTS)} passed")
    print("=" * 60)

    if failed == 0:
        print("[PASS] All Retrieval Judge tests passed.")
    else:
        print(f"[FAIL] {failed} test(s) failed.")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
