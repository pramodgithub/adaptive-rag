from mlflow import trace

from services.retrieval.strategies.graph_strategy import GraphStrategy
from services.retrieval.strategies.vector_strategy import VectorStrategy


class RetrievalPlanner:

    def __init__(self):
        self.vector = VectorStrategy()
        self.graph = GraphStrategy()

    @trace
    def select(self, query: str) -> list[str]:
        query = query.lower()

        graph_signals = [
            "relationship",
            "relationships",
            "related to",
            "depends on",
            "dependency",
            "dependencies",
            "connected to",
            "connection",
            "linked to",
            "maps to",
            "mapped to",
            "traceability",
            "associated with",
            "derived from",
            "runs on",
            "contains",
            "part of",
            "under",
        ]

        control_lookup = any(
            token in query
            for token in [
                "cc",
                "control",
                "requirement",
                "article",
                "section",
            ]
        )

        graph_query = (
            any(signal in query for signal in graph_signals)
            or control_lookup
        )

        if graph_query:
            return ["vector", "graph"]

        return ["vector"]

    @trace
    def get_strategy(self, strategy: str):
        return {
            "vector": self.vector,
            "graph": self.graph,
        }[strategy]
