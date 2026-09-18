from fastapi import FastAPI

from services.retrieval.rag_service import RAGService
from services.retrieval.retrieval_service import RetrievalService
from services.observability.mlflow_service import MLflowService

from apps.api.routes.ingestion import router as ingestion_router


mlflow_service = MLflowService()

app = FastAPI()

retrieval_service = RetrievalService()
rag_service = RAGService()

app.include_router(ingestion_router)


@app.get("/")
def health():
    return {
        "status": "running"
    }


@app.get("/search")
def search(
    query: str,
    top_k: int = 5
):
    return retrieval_service.search(
        query=query,
        top_k=top_k
    )


@app.get("/ask")
def ask(query: str):
    return rag_service.ask(
        query=query
    )
