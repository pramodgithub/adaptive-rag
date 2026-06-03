from mlflow import trace

from database.models.audit import AuditLog
from database.session import SessionLocal


class AuditService:
    @trace
    def save(
        self,
        query: str,
        answer: str,
        retrieval: dict,
        metadata: dict,
        sources: list[str]
    ):

        with SessionLocal() as db:

            audit = AuditLog(
                query=query,
                final_query=retrieval["final_query"],
                answer=answer,
                confidence=retrieval["confidence"],
                retry_count=retrieval["retry_count"],
                model=metadata["model"],
                provider=metadata["provider"],
                latency_ms=metadata["latency_ms"],
                total_tokens=metadata["total_tokens"],
                sources=sources
            )

            db.add(audit)

            db.commit()
