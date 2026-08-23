from __future__ import annotations

from celery import shared_task


@shared_task
def build_graph(document_id: str, nodes: list):
    return {"document_id": document_id, "nodes_count": len(nodes)}
