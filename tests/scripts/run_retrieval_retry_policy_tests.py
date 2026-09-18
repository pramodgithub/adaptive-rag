import traceback

from test_retrieval_retry_policy import (
    test_sufficient_retrieval_generates,
    test_weak_retrieval_rewrites,
    test_borderline_retrieval_runs_judge,
    test_retry_limit_stops_weak_retrieval,
    test_retry_limit_stops_borderline_retrieval,
    test_judge_sufficient_generates,
    test_judge_insufficient_rewrites,
    test_judge_insufficient_at_retry_limit_stops,
)


TESTS = [
    test_sufficient_retrieval_generates,
    test_weak_retrieval_rewrites,
    test_borderline_retrieval_runs_judge,
    test_retry_limit_stops_weak_retrieval,
    test_retry_limit_stops_borderline_retrieval,
    test_judge_sufficient_generates,
    test_judge_insufficient_rewrites,
    test_judge_insufficient_at_retry_limit_stops,
]


def main():
    passed = 0
    failed = 0

    print("=" * 60)
    print("Retrieval Retry Policy Tests")
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

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
