from datetime import datetime, timezone
import logging

from celery import shared_task

from database.session import SessionLocal
from database.models.document import Document
from database.models.document_version import DocumentVersion
from database.models.chunk import Chunk
from database.models.ingestion_job import IngestionJob

from enums.job_status import JobStatus
from enums.processing_status import ProcessingStatus

from services.graph.graph_service import GraphService

logger = logging.getLogger(__name__)


@shared_task(name="ingestion.build_graph")
def build_graph(context: dict):
    document_version_id = context["document_version_id"]
    job_id = context["job_id"]

    db = SessionLocal()
    graph_service = GraphService()

    try:
        document_version = db.get(DocumentVersion, document_version_id)
        job = db.get(IngestionJob, job_id)

        if not document_version:
            raise ValueError("Document version not found")

        if not job:
            raise ValueError("Ingestion job not found")

        document = db.get(Document, document_version.document_id)

        if not document:
            raise ValueError("Document not found")

        chunks = (
            db.query(Chunk)
            .filter(Chunk.document_version_id == document_version_id)
            .order_by(Chunk.chunk_index)
            .all()
        )

        job.status = JobStatus.GRAPH_BUILD
        job.progress = 80
        db.commit()

        graph_counts = graph_service.create_document_graph(
            document,
            document_version,
            chunks,
        )

        # Only a health "pass" becomes searchable. A "review" document is
        # fully built but stays inactive until someone approves it, and any
        # older active version keeps serving search meanwhile.
        health_status = context.get("health_status", "pass")
        activate = health_status == "pass"

        if activate:
            (
                db.query(DocumentVersion)
                .filter(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.id != document_version.id,
                )
                .update({"is_active": False}, synchronize_session=False)
            )
            document_version.is_active = True
            document.active_version_id = document_version.id
        else:
            logger.warning(
                "Document version %s held back from search: health %s (report: %s)",
                document_version_id,
                health_status,
                context.get("health_report_path"),
            )

        document_version.processing_status = ProcessingStatus.READY
        job.progress = 100
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(
            "Graph built for document version %s: %s",
            document_version_id,
            graph_counts,
        )

        return {
            **context,
            "graph_nodes": graph_counts["sections"] + graph_counts["chunks"] + 2,
            "graph": graph_counts,
            "status": "READY" if activate else "NEEDS_REVIEW",
        }

    except Exception as exc:
        db.rollback()

        job = db.get(IngestionJob, job_id)

        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)

        failed_version = db.get(DocumentVersion, document_version_id)

        if failed_version:
            failed_version.processing_status = ProcessingStatus.FAILED

        db.commit()

        logger.exception(
            "Graph build failed for document version: %s",
            document_version_id,
        )

        raise

    finally:
        graph_service.close()
        db.close()
