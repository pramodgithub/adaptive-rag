import json
import logging

from apps.worker.celery_app import celery
from database.models.chunk import Chunk
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob
from database.session import SessionLocal
from enums.job_status import JobStatus
from services.ingestion.chunking.chunk_service import ChunkService

logger = logging.getLogger(__name__)


@celery.task(name="ingestion.chunk_document")
def chunk_document(context: dict):
    document_version_id = context["document_version_id"]
    job_id = context["job_id"]

    logger.info(
        "Chunking document version: %s",
        document_version_id
    )

    db = SessionLocal()
    chunk_service = ChunkService()

    try:
        document_version = db.get(
            DocumentVersion,
            document_version_id
        )
        job = db.get(IngestionJob, job_id)

        if not document_version:
            raise ValueError(
                f"Document version not found: {document_version_id}"
            )

        if not job:
            raise ValueError(
                f"Ingestion job not found: {job_id}"
            )

        with open(
            document_version.parsed_text_path,
            "r",
            encoding="utf-8"
        ) as file:
            parsed = json.load(file)

        chunks = chunk_service.split_pages(parsed["pages"])

        for chunk_data in chunks:
            db.add(
                Chunk(
                    document_version_id=document_version.id,
                    chunk_index=chunk_data.chunk_index,
                    page_number=chunk_data.page_number,
                    text=chunk_data.text
                )
            )

        document_version.chunk_count = len(chunks)
        job.status = JobStatus.EMBEDDING
        job.progress = 50

        db.commit()

        logger.info(
            "Created %s chunks for document version %s",
            len(chunks),
            document_version_id
        )

        return {
            **context,
            "chunk_count": len(chunks)
        }

    except Exception as exc:
        db.rollback()

        job = db.get(IngestionJob, job_id)

        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            db.commit()

        logger.exception(
            "Chunking failed for document version: %s",
            document_version_id
        )

        raise

    finally:
        db.close()
