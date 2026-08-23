from __future__ import annotations

from celery import shared_task


@shared_task
def upsert_vectors(document_id: str, vectors: list):
    return {"document_id": document_id, "vectors_count": len(vectors)}
