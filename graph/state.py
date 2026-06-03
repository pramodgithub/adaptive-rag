from typing import TypedDict


class RAGState(TypedDict):

    execution_id: str

    query: str
    strategies: list[str]

    rewritten_query: str

    retrieved: list
    retrieval: dict

    answer: str
    evaluation: dict
    metadata: dict

    retry_count: int

    retrieval_judge: dict

    all_results: list
    node_metrics: dict
