from graph.workflow import graph


class RAGService:

    def ask(self, query: str):

        result = graph.invoke(
            {
                "query": query,
                "retry_count": 0
            }
        )

        return {
            "answer": result["answer"],
            "strategies": result["strategies"],
            "retrieval": result["retrieval"],
            "evaluation": result["evaluation"],
            "metadata": result["metadata"],
            "sources": [
                x.text
                for x in result["retrieved"]
            ]
        }
