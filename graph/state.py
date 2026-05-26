from typing import TypedDict


class RAGState(TypedDict):

    query: str
    strategies: list[str]

    rewritten_query: str

    retrieved: list
    retrieval: dict

    answer: str
    evaluation: dict
    metadata: dict

    retry_count: int
