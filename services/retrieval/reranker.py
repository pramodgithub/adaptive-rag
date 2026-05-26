class RetrievalReranker:

    SOURCE_WEIGHTS = {
        "tool": 1.2,
        "graph": 1.1,
        "vector": 1.0,
        "web": 0.9
    }

    def rank(self, results):

        for result in results:

            result.score *= (
                self.SOURCE_WEIGHTS[
                    result.source
                ]
            )

        ranked = sorted(
            results,
            key=lambda x: x.score,
            reverse=True
        )

        return ranked[:5]
