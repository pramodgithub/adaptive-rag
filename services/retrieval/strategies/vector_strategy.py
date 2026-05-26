from services.retrieval.retrieval_service import RetrievalService
from services.retrieval.strategies.base import RetrievalStrategy


class VectorStrategy(RetrievalStrategy):

    def __init__(self):

        self.vector_store = RetrievalService()

    def retrieve(self, query: str):

        return self.vector_store.search(query)
