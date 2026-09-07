from mlflow import trace

from database.models.audit import AuditLog
from database.session import SessionLocal


class AuditService:

    @trace
    def save(
        self,
        query: str,
        final_query: str,
        answer: str,
        retrieval_confidence: float,
        retry_count: int,
        metadata: dict,
        sources: list[str],
    ):
        with SessionLocal() as db:
            audit = AuditLog(
                query=query,
                final_query=final_query,
                answer=answer,
                confidence=retrieval_confidence,
                retry_count=retry_count,
                model=metadata["model"],
                provider=metadata["provider"],
                latency_ms=metadata["latency_ms"],
                total_tokens=metadata["total_tokens"],
                sources=sources,
            )

            db.add(audit)
            db.commit()
