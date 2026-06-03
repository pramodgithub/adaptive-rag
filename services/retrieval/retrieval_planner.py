from mlflow import trace

from services.retrieval.strategies.tool_strategy import ToolStrategy
from services.retrieval.strategies.vector_strategy import VectorStrategy
from services.retrieval.strategies.web_strategy import WebStrategy
from services.retrieval.strategies.graph_strategy import GraphStrategy


class RetrievalPlanner:

    def __init__(self):

        self.vector = VectorStrategy()
        self.web = WebStrategy()
        self.graph = GraphStrategy()
        self.tool = ToolStrategy()

    @trace
    def select(self, query: str):

        strategies = []

        query = query.lower()

        graph_keywords = [
            "relationship",
            "connect",
            "dependency",
            "runs"
        ]

        web_keywords = [
            "latest",
            "today",
            "current"
        ]

        tool_keywords = [
            "pod",
            "pods",
            "ec2",
            "cpu",
            "instance",
            "status"
        ]

        if any(x in query for x in tool_keywords):
            strategies.append("tool")

        if any(x in query for x in graph_keywords):
            strategies.append("graph")

        if any(x in query for x in web_keywords):
            strategies.append("web")

        if not strategies:
            strategies.append("vector")

        return strategies

    @trace
    def get_strategy(self, strategy: str):

        return {
            "vector": self.vector,
            "web": self.web,
            "graph": self.graph,
            "tool": self.tool
        }[strategy]
