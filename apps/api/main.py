from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File

from services.ingestion.ingestion_service import IngestionService

from services.retrieval.rag_service import RAGService
from services.retrieval.retrieval_service import RetrievalService

app = FastAPI()

ingestion_service = IngestionService()
retrieval_service = RetrievalService()
rag_service = RAGService()


@app.get("/")
def health():

    return {

        "status": "running"
    }


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...)
):

    content = await file.read()

    text = content.decode(
        "utf-8"
    )

    result = ingestion_service.ingest(

        text=text,
        filename=file.filename
    )

    return result


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
