from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from graph.conditions import should_retry_retrieval
from graph.nodes import audit_node, planner_node
from graph.nodes import evaluate_retrieval_node
from graph.nodes import generate_node
from graph.nodes import retrieve_node
from graph.nodes import rewrite_query_node
from graph.state import RAGState


workflow = StateGraph(RAGState)

workflow.add_node(
    "planner",
    planner_node
)

workflow.add_node(
    "retrieve",
    retrieve_node
)

workflow.add_node(
    "evaluate_retrieval",
    evaluate_retrieval_node
)

workflow.add_node(
    "rewrite",
    rewrite_query_node
)

workflow.add_node(
    "generate",
    generate_node
)

workflow.add_node(
    "audit",
    audit_node
)

# ---------- Edges ---------- #
workflow.add_edge(
    START,
    "planner"
)

workflow.add_edge(
    "planner",
    "retrieve"
)

workflow.add_edge(
    "retrieve",
    "evaluate_retrieval"
)

workflow.add_conditional_edges(
    "evaluate_retrieval",
    should_retry_retrieval,
    {
        "rewrite": "rewrite",
        "generate": "generate"
    }
)

workflow.add_edge(
    "rewrite",
    "retrieve"
)

workflow.add_edge(
    "generate",
    "audit"
)

workflow.add_edge(
    "audit",
    END
)

graph = workflow.compile()
