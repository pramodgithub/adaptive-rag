from core.schemas.retrieval import RetrievalResult
from services.retrieval.query_rewriter import QueryRewriter
from services.retrieval.retrieval_evaluator import RetrievalEvaluator
from services.retrieval.retrieval_service import RetrievalService


class RetryService:

    MAX_RETRIES = 2

    def __init__(self):
        self.retriever = RetrievalService()
        self.evaluator = RetrievalEvaluator()
        self.rewriter = QueryRewriter()

    def retrieve(self, query: str) -> tuple[list[RetrievalResult], dict]:

        current_query = query
        best_results = []
        best_eval = None

        for attempt in range(self.MAX_RETRIES + 1):

            results = self.retriever.search(current_query)
            evaluation = self.evaluator.evaluate(results)

            if not best_eval or evaluation.confidence > best_eval.confidence:
                best_results = results
                best_eval = evaluation

            if not evaluation.should_retry:
                break

            current_query = self.rewriter.rewrite(current_query)

        metadata = {
            "final_query": current_query,
            "confidence": best_eval.confidence,
            "retry_count": attempt
        }

        return best_results, metadata
