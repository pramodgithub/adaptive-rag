from types import SimpleNamespace

from graph.conditions import (
    should_retry_after_judge,
    should_run_retrieval_judge,
)


def retrieval(
    *,
    sufficient,
    confidence,
):
    return SimpleNamespace(
        sufficient=sufficient,
        confidence=confidence,
    )


def judgment(*, sufficient):
    return SimpleNamespace(
        sufficient=sufficient,
    )


def test_sufficient_retrieval_skips_judge():
    state = {
        "retrieval": retrieval(
            sufficient=True,
            confidence=0.90,
        )
    }

    assert should_run_retrieval_judge(state) == "generate"


def test_weak_retrieval_rewrites_without_judge():
    state = {
        "retrieval": retrieval(
            sufficient=False,
            confidence=0.30,
        )
    }

    assert should_run_retrieval_judge(state) == "rewrite"


def test_borderline_retrieval_runs_judge():
    state = {
        "retrieval": retrieval(
            sufficient=False,
            confidence=0.65,
        )
    }

    assert should_run_retrieval_judge(state) == "judge"


def test_judge_says_sufficient():
    state = {
        "retrieval_judgment": judgment(
            sufficient=True,
        )
    }

    assert should_retry_after_judge(state) == "generate"


def test_judge_says_insufficient():
    state = {
        "retrieval_judgment": judgment(
            sufficient=False,
        )
    }

    assert should_retry_after_judge(state) == "rewrite"
