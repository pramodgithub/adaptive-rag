from core.schemas.retrieval import RetrievalResult
from services.retrieval.retrieval_evaluator import RetrievalEvaluator


evaluator = RetrievalEvaluator()

results = [
    RetrievalResult(
        text="Kubernetes orchestrates containers",
        score=0.91
    ),
    RetrievalResult(
        text="Pods are deployable units",
        score=0.82
    )
]

evaluation = evaluator.evaluate(results)

print(evaluation.model_dump())
