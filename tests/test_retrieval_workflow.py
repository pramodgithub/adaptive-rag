from unittest.mock import Mock

from core.schemas.retrieval import RetrievalJudgeResult
from graph.nodes import (
    judge,
    planner,
    reranker,
    retrieval_evaluator,
    rewriter,
    generator,
    audit,
)
from graph.workflow import graph
from apps.rag.state.models import RetrievalEvaluation


def make_result():
    result = Mock()
    result.text = "Access reviews are performed quarterly."
    result.score = 0.80
    result.chunk_id = "chunk-1"
    return result


def make_retrieval_evaluation(
    *,
    sufficient,
    confidence,
):
    return RetrievalEvaluation(
        relevance=confidence,
        coverage=confidence,
        authority=1.0,
        completeness=confidence,
        consistency=1.0,
        confidence=confidence,
        sufficient=sufficient,
        missing_evidence=[] if sufficient else ["Missing evidence"],
        reason=(
            "Evidence is sufficient."
            if sufficient
            else "Evidence is insufficient."
        ),
    )


def make_judgment(*, sufficient):
    return RetrievalJudgeResult(
        relevant=True,
        coverage=0.90 if sufficient else 0.40,
        confidence=0.90 if sufficient else 0.40,
        missing_evidence=[] if sufficient else ["Missing evidence"],
        contradictions=[],
        sufficient=sufficient,
        reason=(
            "Retrieved evidence is sufficient."
            if sufficient
            else "Retrieved evidence is insufficient."
        ),
    )


def base_state():
    return {
        "execution_id": "test-execution",
        "query": "How frequently are access reviews performed?",
        "strategies": [],
        "rewritten_query": "",
        "retrieved": [],
        "all_results": [],
        "retrieval_evaluation": None,
        "retrieval_judgment": None,
        "answer": "",
        "answer_evaluation": None,
        "metadata": {},
        "retry_count": 0,
        "node_metrics": {},
        "assessment_context": None,
    }


def configure_common_mocks():
    strategy = Mock()
    strategy.retrieve = Mock(return_value=[make_result()])

    planner.select = Mock(return_value=["vector"])
    planner.get_strategy = Mock(return_value=strategy)

    reranker.rank = Mock(return_value=[make_result()])

    retrieval_evaluator.evaluate = Mock()
    judge.evaluate = Mock()

    rewriter.rewrite = Mock(
        return_value="What is the frequency of access reviews?"
    )

    generator.generate = Mock(
        return_value=(
            "Access reviews are performed quarterly.",
            {
                "model": "test-model",
                "provider": "test-provider",
                "latency_ms": 10,
                "total_tokens": 50,
            },
            Mock(
                model_dump=Mock(
                    return_value={"status": "passed"}
                )
            ),
        )
    )

    audit.save = Mock(return_value=None)

    return strategy


def test_sufficient_retrieval_skips_judge():
    configure_common_mocks()

    retrieval_evaluator.evaluate.return_value = (
        make_retrieval_evaluation(
            sufficient=True,
            confidence=0.90,
        )
    )

    judge.evaluate.reset_mock()
    generator.generate.reset_mock()
    rewriter.rewrite.reset_mock()
    audit.save.reset_mock()

    state = base_state()

    print("\nBASE STATE:", state)
    print("BASE STATE QUERY:", state.get("query"))

    result = graph.invoke(state)

    assert result["answer"] == (
        "Access reviews are performed quarterly."
    )

    judge.evaluate.assert_not_called()
    rewriter.rewrite.assert_not_called()
    generator.generate.assert_called_once()
    audit.save.assert_called_once()


def test_borderline_retrieval_runs_judge_and_generates():
    configure_common_mocks()

    retrieval_evaluator.evaluate.return_value = (
        make_retrieval_evaluation(
            sufficient=False,
            confidence=0.70,
        )
    )

    judge.evaluate.return_value = make_judgment(
        sufficient=True,
    )

    judge.evaluate.reset_mock()
    generator.generate.reset_mock()
    rewriter.rewrite.reset_mock()
    audit.save.reset_mock()

    result = graph.invoke(base_state())

    assert result["answer"] == (
        "Access reviews are performed quarterly."
    )

    judge.evaluate.assert_called_once()
    rewriter.rewrite.assert_not_called()
    generator.generate.assert_called_once()
    audit.save.assert_called_once()

    assert result["retrieval_judgment"].sufficient is True


def test_judge_insufficient_then_retrieval_succeeds():
    configure_common_mocks()

    retrieval_evaluator.evaluate.side_effect = [
        make_retrieval_evaluation(
            sufficient=False,
            confidence=0.70,
        ),
        make_retrieval_evaluation(
            sufficient=True,
            confidence=0.90,
        ),
    ]

    judge.evaluate.return_value = make_judgment(
        sufficient=False,
    )

    judge.evaluate.reset_mock()
    generator.generate.reset_mock()
    rewriter.rewrite.reset_mock()
    audit.save.reset_mock()

    result = graph.invoke(base_state())

    assert result["answer"] == (
        "Access reviews are performed quarterly."
    )

    assert retrieval_evaluator.evaluate.call_count == 2
    judge.evaluate.assert_called_once()
    rewriter.rewrite.assert_called_once()
    generator.generate.assert_called_once()
    audit.save.assert_called_once()

    assert result["retry_count"] == 1
    assert result["retrieval_evaluation"].sufficient is True


def test_retry_limit_ends_with_insufficient_evidence():
    configure_common_mocks()

    retrieval_evaluator.evaluate.side_effect = [
        make_retrieval_evaluation(
            sufficient=False,
            confidence=0.70,
        ),
        make_retrieval_evaluation(
            sufficient=False,
            confidence=0.70,
        ),
        make_retrieval_evaluation(
            sufficient=False,
            confidence=0.70,
        ),
    ]

    judge.evaluate.return_value = make_judgment(
        sufficient=False,
    )

    judge.evaluate.reset_mock()
    generator.generate.reset_mock()
    rewriter.rewrite.reset_mock()
    audit.save.reset_mock()

    result = graph.invoke(base_state())

    assert (
        result["answer"]
        == "I don't have sufficient evidence in the available "
        "documents to answer this question reliably."
    )

    assert retrieval_evaluator.evaluate.call_count == 3
    assert judge.evaluate.call_count == 2
    assert rewriter.rewrite.call_count == 2

    generator.generate.assert_not_called()
    audit.save.assert_called_once()

    assert result["retry_count"] == 2
