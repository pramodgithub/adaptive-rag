class RetrievalMetrics:
    def relevance(self, results: list[RetrievalResult]) -> float:
        if not results:
            return 0.0

        weights = [1 / (index + 1) for index in range(len(results))]
        weighted_score = sum(
            result.score * weight
            for result, weight in zip(results, weights)
        )

        return round(
            weighted_score / sum(weights),
            3,
        )
