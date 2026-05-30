from core.schemas.retrieval import RetrievalResult
from services.retrieval.strategies.base import RetrievalStrategy


class ToolStrategy(RetrievalStrategy):

    def __init__(self):

        self.tools = {
            "pods": self.get_pods,
            "ec2": self.get_ec2
        }

    def retrieve(
        self,
        query: str
    ):

        query = query.lower()

        for keyword, tool in self.tools.items():

            if keyword in query:

                result = tool()

                return [
                    RetrievalResult(
                        text=result,
                        score=0.95,
                        source="tool"
                    )
                ]

        return []

    def get_pods(self):

        return """
        pod-1 Running
        pod-2 Failed
        pod-3 Running
        """

    def get_ec2(self):

        return """
        instance-1 CPU=85%
        instance-2 CPU=30%
        """
