from test_retrieval_decision import (
    test_sufficient_retrieval_skips_judge,
    test_weak_retrieval_rewrites_without_judge,
    test_borderline_retrieval_runs_judge,
    test_judge_says_sufficient,
    test_judge_says_insufficient,
)


TESTS = [
    test_sufficient_retrieval_skips_judge,
    test_weak_retrieval_rewrites_without_judge,
    test_borderline_retrieval_runs_judge,
    test_judge_says_sufficient,
    test_judge_says_insufficient,
]


def main():
    passed = 0

    print("=" * 60)
    print("Retrieval Decision Tests")
    print("=" * 60)

    for test in TESTS:
        try:
            test()
            passed += 1
            print(f"[PASS] {test.__name__}")
        except Exception as exc:
            print(f"[FAIL] {test.__name__}")
            print(f"       {exc}")

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{len(TESTS)} passed")
    print("=" * 60)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
