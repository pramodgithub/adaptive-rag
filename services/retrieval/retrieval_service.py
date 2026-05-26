from sqlalchemy import text

from core.embeddings.embedding_service import EmbeddingService
from core.schemas.retrieval import RetrievalResult
from database.session import SessionLocal


class RetrievalService:

    def __init__(self):
        self.embedding_service = EmbeddingService()

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:

        embedding = self.embedding_service.embed(query)

        sql = text("""
            SELECT
                text,
                1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM chunks
            ORDER BY score DESC
            LIMIT :top_k
        """)

        with SessionLocal() as db:

            rows = db.execute(
                sql,
                {
                    "embedding": str(embedding),
                    "top_k": top_k
                }
            ).fetchall()

        return [
            RetrievalResult(
                text=row.text,
                score=float(row.score),
                source="vector"
            )
            for row in rows
        ]
