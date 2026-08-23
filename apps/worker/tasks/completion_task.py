from __future__ import annotations

from celery import shared_task


@shared_task
def complete_workflow(document_id: str, status: str = "completed"):
    return {"document_id": document_id, "status": status}
