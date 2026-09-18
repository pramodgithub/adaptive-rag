import os
import uuid
from unittest.mock import patch

from database.models.chunk import Chunk
from database.models.document import Document
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob
from database.session import SessionLocal

from enums.job_status import JobStatus
from enums.processing_status import ProcessingStatus

from apps.worker.celery_app import celery
from apps.worker.tasks.pipeline import start_ingestion


PDF_PATH = "/app/tests/data/CELEX_32016R0679_EN_TXT.pdf"
EMBEDDING_DIMENSION = 1536


def fake_embed(texts):
    return [
        [0.001 * (index + 1)] * EMBEDDING_DIMENSION
        for index, _ in enumerate(texts)
    ]


def test_ingestion_lifecycle():
    db = SessionLocal()

    document = None
    document_version = None
    job = None

    try:
        # ---------------------------------------------------------
        # 1. CREATE DOCUMENT
        # ---------------------------------------------------------

        document = Document(
            title="Ingestion Lifecycle Test GDPR",
            source="test",
            document_type="regulation",
        )

        db.add(document)
        db.flush()

        # ---------------------------------------------------------
        # 2. CREATE DOCUMENT VERSION
        # ---------------------------------------------------------

        document_version = DocumentVersion(
            document_id=document.id,
            version=1,
            is_active=True,
            storage_path=PDF_PATH,
            checksum=str(uuid.uuid4()),
            file_name="CELEX_32016R0679_EN_TXT.pdf",
            mime_type="application/pdf",
            file_size=os.path.getsize(PDF_PATH),
            embedding_model="models/gemini-embedding-2",
            embedding_dimension=EMBEDDING_DIMENSION,
            chunk_count=0,
            processing_status=ProcessingStatus.PROCESSING,
        )

        db.add(document_version)
        db.flush()

        # ---------------------------------------------------------
        # 3. CREATE INGESTION JOB
        # ---------------------------------------------------------

        execution_id = str(uuid.uuid4())

        job = IngestionJob(
            document_version_id=document_version.id,
            status=JobStatus.PENDING,
            progress=0,
            retry_count=0,
            execution_id=execution_id,
        )

        db.add(job)
        db.commit()

        context = {
            "document_version_id": str(document_version.id),
            "job_id": str(job.id),
            "execution_id": execution_id,
        }

        print()
        print("========================================")
        print("INGESTION LIFECYCLE TEST")
        print("========================================")

        print()
        print("INITIAL STATE:")
        print("  execution_id:", execution_id)
        print("  document_id:", document.id)
        print("  document_version_id:", document_version.id)
        print("  job_id:", job.id)
        print("  job_status:", job.status)
        print("  job_progress:", job.progress)
        print(
            "  processing_status:",
            document_version.processing_status,
        )

        # ---------------------------------------------------------
        # 4. VALIDATE INITIAL STATE
        # ---------------------------------------------------------

        assert execution_id is not None
        assert str(job.execution_id) == execution_id

        assert job.status == JobStatus.PENDING
        assert job.progress == 0
        assert job.retry_count == 0

        # ---------------------------------------------------------
        # 5. EXECUTE FULL PIPELINE
        # ---------------------------------------------------------

        print()
        print("========== START INGESTION ==========")

        previous_always_eager = celery.conf.task_always_eager

        celery.conf.task_always_eager = True

        try:
            with patch(
                "apps.worker.tasks.embedding_task.EmbeddingService"
            ) as mock_embedding_service:

                mock_embedding_service.return_value.embed.side_effect = (
                    fake_embed
                )

                result = start_ingestion.run(context)

        finally:
            celery.conf.task_always_eager = previous_always_eager

        print("pipeline result:", result)

        assert result["execution_id"] == execution_id
        assert result["pipeline_task_id"] is not None

        print("pipeline completed")

        # ---------------------------------------------------------
        # 6. REFRESH DATABASE STATE
        # ---------------------------------------------------------

        db.expire_all()

        document = db.get(
            Document,
            document.id,
        )

        document_version = db.get(
            DocumentVersion,
            document_version.id,
        )

        job = db.get(
            IngestionJob,
            job.id,
        )

        chunks = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id
            )
            .order_by(Chunk.chunk_index)
            .all()
        )

        # ---------------------------------------------------------
        # 7. CALCULATE EMBEDDING STATE
        # ---------------------------------------------------------

        embedded_count = sum(
            1
            for chunk in chunks
            if chunk.embedding is not None
        )

        missing_count = sum(
            1
            for chunk in chunks
            if chunk.embedding is None
        )

        # ---------------------------------------------------------
        # 8. FINAL STATE
        # ---------------------------------------------------------

        print()
        print("========== FINAL STATE ==========")

        print("  execution_id:", job.execution_id)
        print("  job_status:", job.status)
        print("  job_progress:", job.progress)

        print(
            "  processing_status:",
            document_version.processing_status,
        )

        print(
            "  chunk_count:",
            document_version.chunk_count,
        )

        print(
            "  actual_chunks:",
            len(chunks),
        )

        print(
            "  embedded_chunks:",
            embedded_count,
        )

        print(
            "  missing_embeddings:",
            missing_count,
        )

        print(
            "  started_at:",
            job.started_at,
        )

        print(
            "  completed_at:",
            job.completed_at,
        )

        # ---------------------------------------------------------
        # 9. EXECUTION IDENTITY
        # ---------------------------------------------------------

        assert str(job.execution_id) == execution_id

        # ---------------------------------------------------------
        # 10. FINAL JOB STATE
        # ---------------------------------------------------------

        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100

        # ---------------------------------------------------------
        # 11. DOCUMENT STATE
        # ---------------------------------------------------------

        assert (
            document_version.processing_status
            == ProcessingStatus.READY
        )

        assert document_version.chunk_count == 180

        # ---------------------------------------------------------
        # 12. CHUNK STATE
        # ---------------------------------------------------------

        assert len(chunks) == 180

        assert embedded_count == 180
        assert missing_count == 0

        # ---------------------------------------------------------
        # 13. EMBEDDING DIMENSION
        # ---------------------------------------------------------

        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == EMBEDDING_DIMENSION

        # ---------------------------------------------------------
        # 14. EXECUTION TIMESTAMPS
        # ---------------------------------------------------------

        assert job.started_at is not None
        assert job.completed_at is not None

        assert job.completed_at >= job.started_at

        # ---------------------------------------------------------
        # 15. DOCUMENT ACTIVE VERSION
        # ---------------------------------------------------------

        assert document.active_version_id == document_version.id

        # ---------------------------------------------------------
        # 16. FINAL SUMMARY
        # ---------------------------------------------------------

        print()
        print("========================================")
        print("INGESTION LIFECYCLE TEST PASSED")
        print("========================================")

        print()
        print("Execution:")
        print("  execution_id:", job.execution_id)
        print("  status:", job.status)
        print("  progress:", job.progress)

        print()
        print("Document:")
        print("  version:", document_version.version)
        print(
            "  processing_status:",
            document_version.processing_status,
        )

        print()
        print("Chunks:")
        print("  total:", len(chunks))
        print("  embedded:", embedded_count)
        print("  missing:", missing_count)

        print()
        print("Lifecycle:")
        print("  started_at:", job.started_at)
        print("  completed_at:", job.completed_at)

    finally:
        # ---------------------------------------------------------
        # CLEANUP
        # ---------------------------------------------------------
        if document_version:
            db.query(Chunk).filter(
                Chunk.document_version_id == document_version.id
            ).delete(
                synchronize_session=False
            )

        if job:
            db.delete(job)

        # Document currently references this version through
        # active_version_id, so clear the FK before deleting it.
        if document:
            document.active_version_id = None
            db.flush()

        if document_version:
            db.delete(document_version)

        if document:
            db.delete(document)

        db.commit()
        db.close()


if __name__ == "__main__":
    test_ingestion_lifecycle()
