import time
from apps.rag.state.models import RetrievalEvaluation
import mlflow
from core.llm.prompts.retrieval_prompt import build_retrieval_prompt

from services.evaluation.answer_retry_service import AnswerRetryService
from services.evaluation.retrieval_judge import RetrievalJudge

from services.retrieval.query_rewriter import QueryRewriter
from services.retrieval.reranker import RetrievalReranker
from services.retrieval.retrieval_evaluator import RetrievalEvaluator
from services.retrieval.retrieval_service import RetrievalService
from services.retrieval.retrieval_planner import RetrievalPlanner

from services.audit.audit_service import AuditService

planner = RetrievalPlanner()
reranker = RetrievalReranker()
retriever = RetrievalService()

retrieval_evaluator = RetrievalEvaluator()
judge = RetrievalJudge()

rewriter = QueryRewriter()
generator = AnswerRetryService()

audit = AuditService()


def planner_node(state):

    start = time.time()
    strategy = planner.select(state["query"])
    duration = round(time.time() - start, 3)
    mlflow.log_metric("planner_duration", duration)
    return {
        "strategies": strategy,   # ← plural, matches RAGState and retrieve_node
        "node_metrics": {
            **state.get("node_metrics", {}),
            "planner": duration
        }
    }


def retrieve_node(state):
    start = time.time()

    query = (
        state.get("rewritten_query")
        or state["query"]
    )

    all_results = []
    retrieved = []

    for strategy_name in state["strategies"]:
        retrieval_strategy = planner.get_strategy(strategy_name)
        results = retrieval_strategy.retrieve(query)
        all_results.extend(results)

    retrieved = reranker.rank(all_results)

    duration = round(time.time() - start, 3)
    mlflow.log_metric("retrieve_duration", duration)

    return {
        "retrieved": retrieved,
        "all_results": all_results,
        "node_metrics": {
            **state.get("node_metrics", {}),
            "retrieve": duration,
        },
    }


def evaluate_retrieval_node(state):
    start = time.time()

    evaluation = retrieval_evaluator.evaluate(
        state["retrieved"],
        state.get("assessment_context"),
    )

    duration = round(time.time() - start, 3)
    mlflow.log_metric("evaluate_retrieval_duration", duration)

    return {
        "retrieval_evaluation": evaluation,
        "node_metrics": {
            **state.get("node_metrics", {}),
            "evaluate_retrieval": duration,
        },
    }


def judge_retrieval_node(state):
    start = time.time()

    query = (
        state.get("rewritten_query")
        or state["query"]
    )

    context = "\n\n".join(
        chunk.text
        for chunk in state["retrieved"]
    )

    judgment = judge.evaluate(
        query=query,
        context=context,
    )

    duration = round(time.time() - start, 3)
    mlflow.log_metric(
        "judge_retrieval_duration",
        duration,
    )

    return {
        "retrieval_judgment": judgment,
        "node_metrics": {
            **state.get("node_metrics", {}),
            "judge_retrieval": duration,
        },
    }


def rewrite_query_node(state):
    start = time.time()

    context = "\n".join(
        chunk.text
        for chunk in state["retrieved"]
    )

    rewritten_query = rewriter.rewrite(
        state["query"],
        context,
    )

    duration = round(time.time() - start, 3)
    mlflow.log_metric(
        "rewrite_query_duration",
        duration,
    )

    return {
        "rewritten_query": rewritten_query,
        "retry_count": state.get("retry_count", 0) + 1,
        "node_metrics": {
            **state.get("node_metrics", {}),
            "rewrite_query": duration,
        },
    }


def generate_node(state):
    start = time.time()
    context = "\n\n".join(
        chunk.text
        for chunk in state["retrieved"]
    )

    prompt = build_retrieval_prompt(
        query=state["query"],
        context=context
    )

    answer, response, evaluation = generator.generate(
        query=state["query"],
        prompt=prompt,
        context=context
    )

    metadata = {
        "model": response["model"],
        "provider": response["provider"],
        "latency_ms": response["latency_ms"],
        "total_tokens": response["total_tokens"]
    }
    duration = round(time.time() - start, 3)
    mlflow.log_metric("generate_duration", duration)
    return {
        "answer": answer,
        "answer_evaluation": evaluation.model_dump(),
        "metadata": metadata,
        "node_metrics": {
            **state.get("node_metrics", {}),
            "generate": duration
        }
    }


def audit_node(state):
    audit.save(
        query=state["query"],
        final_query=state.get("rewritten_query") or state["query"],
        answer=state["answer"],
        retrieval_confidence=state["retrieval_evaluation"].confidence,
        retry_count=state.get("retry_count", 0),
        metadata=state.get("metadata", {}),
        sources=[x.text for x in state["retrieved"]],
    )
    return {}


def insufficient_evidence_node(state):
    retrieval = state.get("retrieval_evaluation")

    reason = (
        retrieval.reason
        if retrieval
        else "Retrieval evidence was insufficient."
    )

    return {
        "answer": (
            "I don't have sufficient evidence in the available "
            "documents to answer this question reliably."
        ),
        "answer_evaluation": {
            "status": "insufficient_evidence",
            "reason": reason,
        },
    }
