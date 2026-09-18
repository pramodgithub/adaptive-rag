from types import SimpleNamespace

from graph.conditions import (
    MAX_RETRIES,
    should_retry_after_judge,
    should_run_retrieval_judge,
)


def retrieval(*, sufficient, confidence):
    return SimpleNamespace(
        sufficient=sufficient,
        confidence=confidence,
        reason="Evidence is insufficient.",
    )


def judgment(*, sufficient):
    return SimpleNamespace(
        sufficient=sufficient,
    )


def test_sufficient_retrieval_generates():
    state = {
        "retrieval": retrieval(
            sufficient=True,
            confidence=0.90,
        ),
        "retry_count": 0,
    }

    assert should_run_retrieval_judge(state) == "generate"


def test_weak_retrieval_rewrites():
    state = {
        "retrieval": retrieval(
            sufficient=False,
            confidence=0.30,
        ),
        "retry_count": 0,
    }

    assert should_run_retrieval_judge(state) == "rewrite"


def test_borderline_retrieval_runs_judge():
    state = {
        "retrieval": retrieval(
            sufficient=False,
            confidence=0.70,
        ),
        "retry_count": 0,
    }

    assert should_run_retrieval_judge(state) == "judge"


def test_retry_limit_stops_weak_retrieval():
    state = {
        "retrieval": retrieval(
            sufficient=False,
            confidence=0.30,
        ),
        "retry_count": MAX_RETRIES,
    }

    assert should_run_retrieval_judge(state) == "insufficient"


def test_retry_limit_stops_borderline_retrieval():
    state = {
        "retrieval": retrieval(
            sufficient=False,
            confidence=0.70,
        ),
        "retry_count": MAX_RETRIES,
    }

    assert should_run_retrieval_judge(state) == "insufficient"


def test_judge_sufficient_generates():
    state = {
        "retrieval_judgment": judgment(
            sufficient=True,
        ),
        "retry_count": 0,
    }

    assert should_retry_after_judge(state) == "generate"


def test_judge_insufficient_rewrites():
    state = {
        "retrieval_judgment": judgment(
            sufficient=False,
        ),
        "retry_count": 0,
    }

    assert should_retry_after_judge(state) == "rewrite"


def test_judge_insufficient_at_retry_limit_stops():
    state = {
        "retrieval_judgment": judgment(
            sufficient=False,
        ),
        "retry_count": MAX_RETRIES,
    }

    assert should_retry_after_judge(state) == "insufficient"
