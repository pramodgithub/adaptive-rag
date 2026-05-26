from core.llm.prompts.retrieval_prompt import build_retrieval_prompt

from services.audit.audit_service import AuditService
from services.evaluation.answer_retry_service import AnswerRetryService
from services.retrieval.query_rewriter import QueryRewriter
from services.retrieval.reranker import RetrievalReranker
from services.retrieval.retrieval_evaluator import RetrievalEvaluator
from services.retrieval.retrieval_service import RetrievalService
from services.retrieval.retrieval_planner import RetrievalPlanner

planner = RetrievalPlanner()
reranker = RetrievalReranker()
retriever = RetrievalService()
retrieval_evaluator = RetrievalEvaluator()

rewriter = QueryRewriter()
generator = AnswerRetryService()

audit = AuditService()


def planner_node(state):
    strategy = planner.select(state["query"])
    return {
        "strategies": strategy   # ← plural, matches RAGState and retrieve_node
    }


def retrieve_node(state):

    query = (
        state.get("rewritten_query")
        or state["query"]
    )

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

        retrieved.extend(results)

    retrieved = reranker.rank(
        retrieved
    )

    return {
        "retrieved": retrieved
    }


def evaluate_retrieval_node(state):

    evaluation = retrieval_evaluator.evaluate(
        state["retrieved"]
    )

    final_query = (
        state.get("rewritten_query")
        or state["query"]
    )

    return {
        "retrieval": {
            "final_query": final_query,
            "confidence": evaluation.confidence,
            "should_retry": evaluation.should_retry,
            "reason": evaluation.reason,
            "retry_count": state["retry_count"]
        }
    }


def rewrite_query_node(state):

    context = "\n".join(
        chunk.text
        for chunk in state["retrieved"]
    )

    rewritten_query = rewriter.rewrite(
        state["query"], context
    )

    return {
        "rewritten_query": rewritten_query,
        "retry_count": state["retry_count"] + 1
    }


def generate_node(state):

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

    return {
        "answer": answer,
        "evaluation": evaluation.model_dump(),
        "metadata": metadata
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
