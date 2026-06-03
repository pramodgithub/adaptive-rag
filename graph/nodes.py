import time
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

        retrieval_strategy = (
            planner.get_strategy(
                strategy_name
            )
        )

        results = (
            retrieval_strategy.retrieve(
                query
            )
        )

        all_results.extend(results)

    retrieved = reranker.rank(
        all_results
    )
    context = "\n\n".join(
        r.text
        for r in retrieved
    )

    judge_evaluation = (
        judge.evaluate(
            query,
            context
        )
    )

    duration = round(time.time() - start, 3)
    mlflow.log_metric("retrieve_duration", duration)
    return {
        "retrieved": retrieved,
        "retrieval_judge": judge_evaluation,
        "all_results": all_results,
        "node_metrics": {
            **state.get("node_metrics", {}),
            "retrieve": duration
        }
    }


def evaluate_retrieval_node(state):
    start = time.time()
    evaluation = retrieval_evaluator.evaluate(
        state["retrieved"]
    )

    final_query = (
        state.get("rewritten_query")
        or state["query"]
    )

    duration = round(time.time() - start, 3)
    mlflow.log_metric("evaluate_retrieval_duration", duration)

    return {
        "retrieval": {
            "final_query": final_query,
            "confidence": evaluation.confidence,
            "should_retry": evaluation.should_retry,
            "reason": evaluation.reason,
            "retry_count": state["retry_count"]
        },
        "node_metrics": {
            **state.get("node_metrics", {}),
            "evaluate_retrieval": duration
        }
    }


def rewrite_query_node(state):
    start = time.time()
    context = "\n".join(
        chunk.text
        for chunk in state["retrieved"]
    )

    rewritten_query = rewriter.rewrite(
        state["query"], context
    )

    duration = round(time.time() - start, 3)
    mlflow.log_metric("rewrite_query_duration", duration)

    return {
        "rewritten_query": rewritten_query,
        "retry_count": state["retry_count"] + 1,
        "node_metrics": {
            **state.get("node_metrics", {}),
            "rewrite_query": duration
        }
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
        "evaluation": evaluation.model_dump(),
        "metadata": metadata,
        "node_metrics": {
            **state.get("node_metrics", {}),
            "generate": duration
        }
    }


def audit_node(state):

    audit.save(
        query=state["query"],
        answer=state["answer"],
        retrieval=state["retrieval"],
        metadata=state["metadata"],
        sources=[x.text for x in state["retrieved"]]
    )

    return {}
