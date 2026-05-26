from langchain_tavily import TavilySearch

from core.schemas.retrieval import RetrievalResult
from services.retrieval.strategies.base import RetrievalStrategy


class WebStrategy(RetrievalStrategy):

    def __init__(self):

        self.search = TavilySearch(
            max_results=5
        )

    def retrieve(self, query: str):

        response = self.search.invoke(query)

        results = response.get("results", [])

        return [
            RetrievalResult(
                text=result["content"],
                score=result["score"],
                source="web"
                # url=result["url"],
                # title=result["title"]
            )
            for result in results
        ]
