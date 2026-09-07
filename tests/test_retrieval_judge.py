from unittest.mock import Mock

from core.schemas.retrieval import RetrievalJudgeResult
from services.evaluation.retrieval_judge import RetrievalJudge
from services.evaluation.retrieval_judge_parser import RetrievalJudgeParser


def create_judge(response_text: str):
    llm = Mock()
    llm.generate_for_node.return_value = {
        "text": response_text,
    }

    return RetrievalJudge(llm=llm)


def test_sufficient_evidence():
    judge = create_judge(
        """
        {
            "relevant": true,
            "coverage": 0.95,
            "confidence": 0.94,
            "missing_evidence": [],
            "contradictions": [],
            "sufficient": true,
            "reason": "The retrieved evidence directly answers the question."
        }
        """
    )

    result = judge.evaluate(
        query="How frequently is security awareness training conducted?",
        context="Security awareness training is conducted annually.",
    )

    assert isinstance(result, RetrievalJudgeResult)
    assert result.relevant is True
    assert result.coverage == 0.95
    assert result.confidence == 0.94
    assert result.missing_evidence == []
    assert result.contradictions == []
    assert result.sufficient is True


def test_relevant_but_incomplete_evidence():
    judge = create_judge(
        """
        {
            "relevant": true,
            "coverage": 0.55,
            "confidence": 0.62,
            "missing_evidence": [
                "The frequency of the training is not specified."
            ],
            "contradictions": [],
            "sufficient": false,
            "reason": "The context discusses training but does not establish its frequency."
        }
        """
    )

    result = judge.evaluate(
        query="How frequently is security awareness training conducted?",
        context="Employees receive security awareness training.",
    )

    assert result.relevant is True
    assert result.coverage == 0.55
    assert result.sufficient is False
    assert len(result.missing_evidence) == 1


def test_missing_evidence():
    judge = create_judge(
        """
        {
            "relevant": true,
            "coverage": 0.40,
            "confidence": 0.45,
            "missing_evidence": [
                "The required retention period is missing."
            ],
            "contradictions": [],
            "sufficient": false,
            "reason": "The retrieved evidence does not specify the retention period."
        }
        """
    )

    result = judge.evaluate(
        query="How long are audit logs retained?",
        context="Audit logs are collected and monitored.",
    )

    assert result.sufficient is False
    assert "retention period" in result.missing_evidence[0]


def test_contradictory_evidence():
    judge = create_judge(
        """
        {
            "relevant": true,
            "coverage": 0.80,
            "confidence": 0.30,
            "missing_evidence": [],
            "contradictions": [
                "One document states that access reviews occur quarterly while another states annually."
            ],
            "sufficient": false,
            "reason": "The retrieved evidence contains conflicting review frequencies."
        }
        """
    )

    result = judge.evaluate(
        query="How frequently are access reviews performed?",
        context="""
        Access reviews are performed quarterly.

        Access reviews are performed annually.
        """,
    )

    assert result.relevant is True
    assert result.sufficient is False
    assert len(result.contradictions) == 1


def test_irrelevant_evidence():
    judge = create_judge(
        """
        {
            "relevant": false,
            "coverage": 0.05,
            "confidence": 0.95,
            "missing_evidence": [
                "Evidence describing access management controls."
            ],
            "contradictions": [],
            "sufficient": false,
            "reason": "The retrieved context discusses physical security rather than access management."
        }
        """
    )

    result = judge.evaluate(
        query="How is administrative access protected?",
        context="The organization maintains physical security controls.",
    )

    assert result.relevant is False
    assert result.sufficient is False


def test_malformed_json():
    result = RetrievalJudgeParser.parse(
        '{"relevant": true, "coverage":'
    )

    assert isinstance(result, RetrievalJudgeResult)
    assert result.sufficient is False
    assert result.confidence == 0.0
    assert result.reason == "Invalid retrieval judge response."


def test_invalid_field_values():
    result = RetrievalJudgeParser.parse(
        """
        {
            "relevant": true,
            "coverage": 1.5,
            "confidence": 0.8,
            "missing_evidence": [],
            "contradictions": [],
            "sufficient": true,
            "reason": "Invalid coverage."
        }
        """
    )

    assert isinstance(result, RetrievalJudgeResult)
    assert result.sufficient is False
    assert result.confidence == 0.0
    assert result.reason == "Invalid retrieval judge response."


def test_missing_required_field():
    result = RetrievalJudgeParser.parse(
        """
        {
            "relevant": true,
            "coverage": 0.8,
            "confidence": 0.8,
            "missing_evidence": [],
            "contradictions": [],
            "sufficient": true
        }
        """
    )

    assert isinstance(result, RetrievalJudgeResult)
    assert result.sufficient is False
    assert result.reason == "Invalid retrieval judge response."


def test_llm_failure_is_propagated():
    llm = Mock()

    llm.generate_for_node.side_effect = RuntimeError(
        "LLM provider unavailable"
    )

    judge = RetrievalJudge(llm=llm)

    try:
        judge.evaluate(
            query="How is administrative access protected?",
            context="Administrative access is restricted.",
        )
    except RuntimeError as exc:
        assert str(exc) == "LLM provider unavailable"
        return

    raise AssertionError("Expected RuntimeError was not raised.")


def test_parser_valid_response():
    result = RetrievalJudgeParser.parse(
        """
        {
            "relevant": true,
            "coverage": 0.90,
            "confidence": 0.88,
            "missing_evidence": [],
            "contradictions": [],
            "sufficient": true,
            "reason": "The retrieved evidence directly answers the question."
        }
        """
    )

    assert isinstance(result, RetrievalJudgeResult)
    assert result.relevant is True
    assert result.coverage == 0.90
    assert result.confidence == 0.88
    assert result.sufficient is True
