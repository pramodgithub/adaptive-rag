from sqlalchemy import text

from core.embeddings.embedding_service import EmbeddingService
from core.schemas.retrieval import RetrievalResult
from database.session import SessionLocal
from enums.document_status import DocumentStatus
from enums.processing_status import ProcessingStatus


class RetrievalService:

    def __init__(self):
        self.embedding_service = EmbeddingService()

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:

        embedding = self.embedding_service.embed(query)[0]

        sql = text("""
            SELECT
                c.id AS chunk_id,
                c.document_version_id,
                dv.document_id,
                c.text,
                c.chunk_index,
                c.page_number,
                d.title,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM chunks c
            JOIN document_versions dv
                ON dv.id = c.document_version_id
            JOIN documents d
                ON d.id = dv.document_id
            WHERE c.embedding IS NOT NULL
            AND d.status = :document_status
            AND dv.is_active = TRUE
            AND dv.processing_status = :processing_status
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)

        with SessionLocal() as db:

            rows = db.execute(
                sql,
                {
                    "embedding": str(embedding),
                    "document_status": DocumentStatus.ACTIVE.value,
                    "processing_status": ProcessingStatus.READY.value,
                    "top_k": top_k
                }
            ).fetchall()

        return [
            RetrievalResult(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_version_id=row.document_version_id,
                chunk_index=row.chunk_index,
                page_number=row.page_number,
                document_title=row.title,
                text=row.text,
                score=float(row.score),
                source="vector"
            )
            for row in rows
        ]
