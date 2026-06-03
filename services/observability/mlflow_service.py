import mlflow
from mlflow import trace


class MLflowService:

    def __init__(self):

        mlflow.set_tracking_uri(
            "http://mlflow:5000"
        )

        mlflow.set_experiment(
            "adaptive-rag"
        )
