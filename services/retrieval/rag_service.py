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
            "retrieved": [
                {
                    "source": r.source,
                    "score": r.score,
                    "text": r.text[:200]
                }
                for r in result["retrieved"]
            ],
            "retrieval_stats": {

                "before_rerank": len(result["all_results"]),

                "after_rerank": len(result["retrieved"]),

                "sources": {

                    "tool": len(
                        [
                            r
                            for r in result["retrieved"]
                            if r.source == "tool"
                        ]
                    ),

                    "web": len(
                        [
                            r
                            for r in result["retrieved"]
                            if r.source == "web"
                        ]
                    ),

                    "graph": len(
                        [
                            r
                            for r in result["retrieved"]
                            if r.source == "graph"
                        ]
                    ),

                    "vector": len(
                        [
                            r
                            for r in result["retrieved"]
                            if r.source == "vector"
                        ]
                    )
                }
            },
            "evaluation": result["evaluation"],
            "metadata": result["metadata"],
            "sources": [
                x.text
                for x in result["retrieved"]
            ]
        }
