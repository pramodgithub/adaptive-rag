import logging

from database.session import SessionLocal
from apps.worker.celery_app import celery
from services.ingestion.chunking.chunk_persistence_service import ChunkPersistenceService

logger = logging.getLogger(__name__)


@celery.task(name="ingestion.persist_chunks")
def persist_chunks(context: dict):

    db = SessionLocal()

    try:
        service = ChunkPersistenceService()

        count = service.save(
            db=db,
            document_version_id=context["document_version_id"],
            chunks=context["embedded_chunks"]
        )

        db.commit()

        logger.info(
            "Persisted %s chunks for document version %s",
            count,
            context["document_version_id"]
        )

        context["chunk_count"] = count

        return context

    except Exception:
        db.rollback()
        logger.exception(
            "Failed to persist chunks for document version %s",
            context["document_version_id"]
        )
        raise

    finally:
        db.close()
