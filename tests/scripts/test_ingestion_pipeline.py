import json
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


def test_full_ingestion_pipeline():
    db = SessionLocal()

    document = None
    document_version = None
    job = None

    try:
        document = Document(
            title="Full Pipeline Test GDPR",
            source="test",
            document_type="regulation",
        )
        db.add(document)
        db.flush()

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

        job = IngestionJob(
            document_version_id=document_version.id,
            status=JobStatus.PENDING,
            progress=0,
            execution_id=str(uuid.uuid4()),
        )
        db.add(job)
        db.commit()

        context = {
            "document_version_id": str(document_version.id),
            "job_id": str(job.id),
            "execution_id": job.execution_id,
        }

        print()
        print("========================================")
        print("FULL INGESTION PIPELINE")
        print("========================================")
        print("document_version_id:", document_version.id)
        print("job_id:", job.id)

        print()
        print("========== START PIPELINE ==========")

        previous_always_eager = celery.conf.task_always_eager

        celery.conf.task_always_eager = True

        try:
            with patch(
                "apps.worker.tasks.embedding_task.EmbeddingService"
            ) as mock_embedding_service:

                mock_embedding_service.return_value.embed.side_effect = fake_embed

                result = start_ingestion.run(context)

        finally:
            celery.conf.task_always_eager = previous_always_eager

        print("pipeline result:", result)

        assert "execution_id" in result
        assert "pipeline_task_id" in result

        print()
        print("Pipeline completed.")

        db.expire_all()

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

        print()
        print("========== FINAL STATE ==========")
        print(
            "processing_status:",
            document_version.processing_status,
        )
        print(
            "job_status:",
            job.status,
        )
        print(
            "job_progress:",
            job.progress,
        )
        print(
            "chunk_count:",
            document_version.chunk_count,
        )
        print(
            "actual chunks:",
            len(chunks),
        )

        embedded_count = sum(
            1 for chunk in chunks
            if chunk.embedding is not None
        )

        missing_count = sum(
            1 for chunk in chunks
            if chunk.embedding is None
        )

        print(
            "embedded chunks:",
            embedded_count,
        )
        print(
            "missing embeddings:",
            missing_count,
        )

        assert document_version.processing_status == ProcessingStatus.READY
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100

        assert document_version.chunk_count == 180
        assert len(chunks) == 180

        assert embedded_count == 180
        assert missing_count == 0

        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == EMBEDDING_DIMENSION

        print()
        print("========================================")
        print("FULL INGESTION PIPELINE TEST PASSED")
        print("========================================")

    finally:
        if document_version:
            db.query(Chunk).filter(
                Chunk.document_version_id == document_version.id
            ).delete(synchronize_session=False)

        if job:
            db.delete(job)

        if document_version:
            db.delete(document_version)

        if document:
            db.delete(document)

        db.commit()
        db.close()


if __name__ == "__main__":
    test_full_ingestion_pipeline()
