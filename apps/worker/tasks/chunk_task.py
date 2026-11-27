import json
import logging

from apps.worker.celery_app import celery
from database.models.chunk import Chunk
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob
from database.session import SessionLocal
from enums.job_status import JobStatus
from enums.processing_status import ProcessingStatus

from services.ingestion.domain.serialization import document_from_dict
from services.ingestion.parsers.chunk_candidate import ChunkCandidate
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
)
from services.ingestion.chunking.chunker import ComplianceChunker
from services.ingestion.chunking.health import build_health_report
from services.storage.file_storage import FileStorage
from services.ingestion.semantics.extractor import SemanticEntityExtractor
from services.ingestion.semantics.persistence import (
    SemanticEntityPersistenceService,
)
from database.models.chunk_semantic_entity import ChunkSemanticEntity

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
    semantic_entities_saved = 0

    semantic_extractor = SemanticEntityExtractor()
    semantic_persistence = SemanticEntityPersistenceService()

    for chunk in chunks:
        generated_indexes.add(chunk.chunk_index)

        existing = existing_by_index.get(chunk.chunk_index)

        if existing:
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

            db.flush()
            persisted_chunk = existing

            updated += 1

        else:
            persisted_chunk = Chunk(
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

            db.add(persisted_chunk)
            db.flush()

            inserted += 1

        # Rebuild semantic entities on every reconciliation so changes in
        # text or structural context cannot leave stale semantic records.
        db.query(ChunkSemanticEntity).filter(
            ChunkSemanticEntity.chunk_id == persisted_chunk.id
        ).delete(synchronize_session=False)

        entities = semantic_extractor.extract(chunk)

        semantic_entities_saved += semantic_persistence.save(
            db=db,
            chunk=persisted_chunk,
            entities=entities,
        )

    obsolete_chunks = [
        chunk
        for chunk in existing_chunks
        if chunk.chunk_index not in generated_indexes
    ]

    for chunk in obsolete_chunks:
        db.delete(chunk)

    logger.info(
        "Chunk reconciliation: inserted=%s updated=%s deleted=%s "
        "semantic_entities=%s",
        inserted,
        updated,
        len(obsolete_chunks),
        semantic_entities_saved,
    )

    return {
        "inserted": inserted,
        "updated": updated,
        "deleted": len(obsolete_chunks),
        "total": len(chunks),
        "semantic_entities": semantic_entities_saved,
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

        candidates = [
            ChunkCandidate(
                text=item["text"],
                source_refs=item.get("source_refs", []),
                page_start=item.get("page_start"),
                page_end=item.get("page_end"),
                headings=item.get("headings", []),
            )
            for item in parsed.get("chunk_candidates", [])
        ]

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
            structured_document,
            candidates,
        )

        logger.info(
            "Generated %s document chunks for document version %s",
            len(chunks),
            document_version_id,
        )

        # Health check before anything is saved. "fail" stops here, so a
        # broken result never reaches the database or search.
        health = build_health_report(structured_document, candidates, chunks)
        health_path = FileStorage().save_json(
            health,
            f"{document_version.file_name}.health",
        )
        logger.info(
            "Health %s for document version %s: %s (report: %s)",
            health["status"].upper(),
            document_version_id,
            health["summary"],
            health_path,
        )

        if health["status"] == "fail":
            raise ValueError(
                f"Health check failed: {health['summary']} (report: {health_path})"
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
            "health_status": health["status"],
            "health_report_path": health_path,
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

        failed_version = db.get(
            DocumentVersion,
            document_version_id,
        )

        if failed_version:
            failed_version.processing_status = ProcessingStatus.FAILED

        db.commit()

        logger.exception(
            "Chunking failed for document version: %s",
            document_version_id,
        )

        raise

    finally:
        db.close()
