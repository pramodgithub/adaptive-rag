from langgraph.graph import END, START, StateGraph

from graph.conditions import (
    should_retry_after_judge,
    should_run_retrieval_judge,
)
from graph.nodes import (
    audit_node,
    evaluate_retrieval_node,
    generate_node,
    insufficient_evidence_node,
    judge_retrieval_node,
    planner_node,
    retrieve_node,
    rewrite_query_node,
)
from graph.state import RAGState


workflow = StateGraph(RAGState)

# ---------- Nodes ----------

workflow.add_node("planner", planner_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node(
    "evaluate_retrieval",
    evaluate_retrieval_node,
)
workflow.add_node(
    "judge_retrieval",
    judge_retrieval_node,
)
workflow.add_node("rewrite", rewrite_query_node)
workflow.add_node("generate", generate_node)
workflow.add_node(
    "insufficient",
    insufficient_evidence_node,
)
workflow.add_node("audit", audit_node)


# ---------- Edges ----------

workflow.add_edge(START, "planner")
workflow.add_edge("planner", "retrieve")
workflow.add_edge(
    "retrieve",
    "evaluate_retrieval",
)

workflow.add_conditional_edges(
    "evaluate_retrieval",
    should_run_retrieval_judge,
    {
        "judge": "judge_retrieval",
        "rewrite": "rewrite",
        "generate": "generate",
        "insufficient": "insufficient",
    },
)

workflow.add_conditional_edges(
    "judge_retrieval",
    should_retry_after_judge,
    {
        "rewrite": "rewrite",
        "generate": "generate",
        "insufficient": "insufficient",
    },
)

workflow.add_edge("rewrite", "retrieve")
workflow.add_edge("generate", "audit")
workflow.add_edge("insufficient", "audit")
workflow.add_edge("audit", END)


graph = workflow.compile()
