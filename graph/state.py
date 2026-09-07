from typing import TypedDict

from apps.rag.state.models import AssessmentContext, RetrievalEvaluation
from core.schemas.retrieval import RetrievalJudgeResult


class RAGState(TypedDict, total=False):
    execution_id: str
    query: str

    strategies: list[str]
    rewritten_query: str

    retrieved: list
    all_results: list

    retrieval_evaluation: RetrievalEvaluation | None
    retrieval_judgment: RetrievalJudgeResult | None

    answer: str
    answer_evaluation: dict | None

    metadata: dict
    retry_count: int
    node_metrics: dict

    assessment_context: AssessmentContext | None
