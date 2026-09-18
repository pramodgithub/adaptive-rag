import json
import logging

from apps.worker.celery_app import celery
from database.models.chunk import Chunk
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob
from database.session import SessionLocal
from enums.job_status import JobStatus

from services.ingestion.domain.serialization import document_from_dict
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
)
from services.ingestion.chunking.chunker import ComplianceChunker

logger = logging.getLogger(__name__)


def _persist_chunks(db, document_version_id, chunks):
    existing_chunks = (
        db.query(Chunk)
        .filter(
            Chunk.document_version_id == document_version_id
        )
        .all()
    )

    existing_by_index = {
        chunk.chunk_index: chunk
        for chunk in existing_chunks
    }

    generated_indexes = set()

    inserted = 0
    updated = 0

    for chunk in chunks:
        generated_indexes.add(chunk.chunk_index)

        existing = existing_by_index.get(chunk.chunk_index)

        if existing:
            text_changed = existing.text != chunk.text

            existing.page_number = chunk.page_start
            existing.page_start = chunk.page_start
            existing.page_end = chunk.page_end
            existing.text = chunk.text
            existing.section_path = chunk.section_path
            existing.structure_type = chunk.structure_type
            existing.identifier = chunk.identifier
            existing.parent_identifier = chunk.parent_identifier
            existing.element_indexes = chunk.element_indexes
            existing.chunk_metadata = chunk.metadata

            if text_changed:
                existing.embedding = None

            updated += 1

        else:
            db.add(
                Chunk(
                    document_version_id=document_version_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_start,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text=chunk.text,
                    section_path=chunk.section_path,
                    structure_type=chunk.structure_type,
                    identifier=chunk.identifier,
                    parent_identifier=chunk.parent_identifier,
                    element_indexes=chunk.element_indexes,
                    chunk_metadata=chunk.metadata,
                )
            )

            inserted += 1

    obsolete_chunks = [
        chunk
        for chunk in existing_chunks
        if chunk.chunk_index not in generated_indexes
    ]

    for chunk in obsolete_chunks:
        db.delete(chunk)

    logger.info(
        "Chunk reconciliation: inserted=%s updated=%s deleted=%s",
        inserted,
        updated,
        len(obsolete_chunks),
    )

    return {
        "inserted": inserted,
        "updated": updated,
        "deleted": len(obsolete_chunks),
        "total": len(chunks),
    }


@celery.task(name="ingestion.chunk_document")
def chunk_document(context: dict):
    document_version_id = context["document_version_id"]
    job_id = context["job_id"]

    logger.info(
        "Chunking document version: %s",
        document_version_id,
    )

    db = SessionLocal()

    structure_inference = StructureInferenceService()
    chunker = ComplianceChunker()

    try:
        document_version = db.get(
            DocumentVersion,
            document_version_id,
        )

        job = db.get(
            IngestionJob,
            job_id,
        )

        if not document_version:
            raise ValueError(
                f"Document version not found: {document_version_id}"
            )

        if not job:
            raise ValueError(
                f"Ingestion job not found: {job_id}"
            )

        if not document_version.parsed_text_path:
            raise ValueError(
                f"Parsed document not found for version: "
                f"{document_version_id}"
            )

        with open(
            document_version.parsed_text_path,
            "r",
            encoding="utf-8",
        ) as file:
            parsed = json.load(file)

        document = document_from_dict(parsed)

        logger.info(
            "Loaded canonical document: title=%s elements=%s pages=%s",
            document.title,
            len(document.elements),
            document.page_count,
        )

        structured_document = structure_inference.infer(
            document
        )

        chunks = chunker.chunk(
            structured_document
        )

        logger.info(
            "Generated %s compliance chunks for document version %s",
            len(chunks),
            document_version_id,
        )

        reconciliation = _persist_chunks(
            db,
            document_version.id,
            chunks,
        )

        document_version.chunk_count = reconciliation["total"]

        job.status = JobStatus.EMBEDDING
        job.progress = 50

        db.commit()

        logger.info(
            "Chunk persistence completed for document version %s: "
            "inserted=%s updated=%s deleted=%s total=%s",
            document_version_id,
            reconciliation["inserted"],
            reconciliation["updated"],
            reconciliation["deleted"],
            reconciliation["total"],
        )

        return {
            **context,
            "chunk_count": reconciliation["total"],
            "inserted": reconciliation["inserted"],
            "updated": reconciliation["updated"],
            "deleted": reconciliation["deleted"],
        }

    except Exception as exc:
        db.rollback()

        job = db.get(
            IngestionJob,
            job_id,
        )

        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            db.commit()

        logger.exception(
            "Chunking failed for document version: %s",
            document_version_id,
        )

        raise

    finally:
        db.close()
