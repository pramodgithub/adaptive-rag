import mlflow
import uuid
from graph.workflow import graph


class RAGService:

    def ask(self, query: str):
        execution_id = str(uuid.uuid4())
        with mlflow.start_run():

            mlflow.set_tag("execution_id", execution_id)
            # log the input query
            mlflow.log_param("query", query)

            result = graph.invoke(
                {
                    "query": query,
                    "retry_count": 0,
                    "execution_id": execution_id,
                    "node_metrics": {}
                }
            )

            # evaluation scores
            evaluation = result["evaluation"]
            mlflow.log_metrics({
                "confidence":   evaluation.get("confidence", 0),
                "grounded":     int(evaluation.get("grounded", False)),
                "should_retry": int(evaluation.get("should_retry", False)),
                "retry_count":  result.get("retry_count", 0),
            })

            # retrieval stats
            retrieved = result["retrieved"]
            all_results = result["all_results"]
            mlflow.log_metrics({
                "before_rerank": len(all_results),
                "after_rerank":  len(retrieved),
            })

            mlflow.log_metric(
                "retrieval_confidence",
                # score of top ranked chunk
                retrieved[0].score if retrieved else 0
            )

            # judge confidence
            retrieval_judge = result["retrieval_judge"]  # now a dict
            mlflow.log_metrics({
                "judge_confidence":  retrieval_judge.confidence,
                "judge_coverage":    retrieval_judge.coverage,
                "judge_relevant":    int(retrieval_judge.relevant),
            })
            # source counts
            source_stats = {}
            for r in retrieved:
                source_stats[r.source] = (
                    source_stats.get(r.source, 0) + 1
                )
            for source, count in source_stats.items():
                mlflow.log_metric(f"source_{source}", count)

            # strategies used
            mlflow.set_tag(
                "strategies",
                ",".join(result["strategies"])
            )

        return {
            "execution_id": result["execution_id"],
            "answer": result["answer"],
            "strategies": result["strategies"],
            "retrieved": [
                {
                    "source": r.source,
                    "score": r.score,
                    "text": r.text[:200]
                }
                for r in retrieved
            ],
            "retrieval_stats": {
                "before_rerank": len(all_results),
                "after_rerank":  len(retrieved),
                "sources": source_stats
            },
            "evaluation": result["evaluation"],
            "metadata": result["metadata"],
            "sources": [
                x.text
                for x in retrieved
            ],
            "node_metrics": result["node_metrics"]
        }
