import logging

from database.session import SessionLocal
from database.models.chunk import Chunk
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob
from enums.job_status import JobStatus
from core.embeddings.embedding_service import EmbeddingService

from apps.worker.celery_app import celery
from enums.processing_status import ProcessingStatus

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


@celery.task(name="ingestion.embed_document")
def embed_document(context: dict):
    document_version_id = context["document_version_id"]
    job_id = context["job_id"]

    logger.info(
        "Embedding document version: %s",
        document_version_id
    )

    db = SessionLocal()
    embedding_service = EmbeddingService()

    try:
        document_version = db.get(
            DocumentVersion,
            document_version_id
        )

        job = db.get(
            IngestionJob,
            job_id
        )

        if not document_version:
            raise ValueError("Document version not found")

        if not job:
            raise ValueError("Ingestion job not found")

        chunks = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version_id,
                Chunk.embedding.is_(None)
            )
            .order_by(Chunk.chunk_index)
            .all()
        )

        logger.info(
            "Found %s chunks requiring embeddings",
            len(chunks)
        )

        total_chunks = len(chunks)

        if not total_chunks:
            document_version.processing_status = ProcessingStatus.READY
            job.progress = 100
            job.status = JobStatus.COMPLETED
            db.commit()

            return {
                **context,
                "embedded_count": 0,
                "status": ProcessingStatus.READY.value
            }

        embedded_count = 0

        for start in range(0, total_chunks, BATCH_SIZE):
            batch = chunks[start:start + BATCH_SIZE]

            logger.info(
                "Embedding batch: %s-%s of %s",
                start + 1,
                start + len(batch),
                total_chunks
            )

            texts = [chunk.text for chunk in batch]

            embeddings = embedding_service.embed(texts)

            if len(embeddings) != len(batch):
                raise ValueError(
                    f"Embedding count mismatch: expected {len(batch)}, "
                    f"got {len(embeddings)}"
                )

            for chunk, embedding in zip(batch, embeddings):
                chunk.embedding = embedding

            db.commit()

            embedded_count += len(batch)

            progress = 50 + int(
                (embedded_count / total_chunks) * 25
            )

            job.progress = min(progress, 75)
            db.commit()

        if embedded_count != total_chunks:
            raise RuntimeError(
                f"Embedding incomplete: {embedded_count}/{total_chunks}"
            )

        document_version.processing_status = ProcessingStatus.READY
        job.progress = 100
        job.status = JobStatus.COMPLETED

        db.commit()

        logger.info(
            "Document version %s is READY",
            document_version_id
        )

        return {
            **context,
            "embedded_count": embedded_count,
            "status": ProcessingStatus.READY.value
        }

    except Exception as exc:
        db.rollback()

        document_version = db.get(
            DocumentVersion,
            document_version_id
        )

        job = db.get(
            IngestionJob,
            job_id
        )

        if document_version:
            document_version.processing_status = ProcessingStatus.FAILED

        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)

        db.commit()

        logger.exception(
            "Embedding failed for document version: %s",
            document_version_id
        )

        raise

    finally:
        db.close()
