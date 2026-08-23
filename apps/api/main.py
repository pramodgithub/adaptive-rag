from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File

from services.ingestion.ingestion_service import IngestionService

from services.retrieval.rag_service import RAGService
from services.retrieval.retrieval_service import RetrievalService
from services.observability.mlflow_service import MLflowService

mlflow_service = MLflowService()

app = FastAPI()

ingestion_service = IngestionService()
retrieval_service = RetrievalService()
rag_service = RAGService()


@app.get("/")
def health():

    return {

        "status": "running"
    }


@app.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...)
):
    return await ingestion_service.create_ingestion(file)


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
