import traceback

from test_retrieval_workflow import (
    test_sufficient_retrieval_skips_judge,
    test_borderline_retrieval_runs_judge_and_generates,
    test_judge_insufficient_then_retrieval_succeeds,
    test_retry_limit_ends_with_insufficient_evidence,
)


TESTS = [
    test_sufficient_retrieval_skips_judge,
    test_borderline_retrieval_runs_judge_and_generates,
    test_judge_insufficient_then_retrieval_succeeds,
    test_retry_limit_ends_with_insufficient_evidence,
]


def main():
    passed = 0
    failed = 0

    print("=" * 60)
    print("Retrieval Workflow Integration Tests")
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
        print("[PASS] All Retrieval Workflow tests passed.")
    else:
        print(f"[FAIL] {failed} test(s) failed.")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
