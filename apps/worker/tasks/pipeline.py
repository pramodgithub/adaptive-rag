from celery import chain

from apps.worker.celery_app import celery
from apps.worker.tasks.parse_task import parse_document
from apps.worker.tasks.chunk_task import chunk_document
from apps.worker.tasks.persist_chunks_task import persist_chunks
from apps.worker.tasks.embedding_task import embed_document


@celery.task(name="ingestion.start")
def start_ingestion(context: dict):

    workflow = chain(
        parse_document.s(context),
        chunk_document.s(),
        embed_document.s()
    )

    result = workflow.apply_async()

    return {
        "execution_id": context["execution_id"],
        "pipeline_task_id": result.id
    }


# chain(
#     parse_document.s(),
#     chunk_document.s(),
#     embed_document.s(),
#     store_vectors.s(),
#     build_graph.s(),
#     complete_ingestion.s()
# ).apply_async(
#     args=[context]
# )
