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

from apps.worker.tasks.chunk_task import chunk_document
from apps.worker.tasks.embedding_task import embed_document
from services.ingestion.domain.serialization import document_to_dict
from services.ingestion.parsers.factory import ParserFactory

import json


PDF_PATH = "/app/tests/data/CELEX_32016R0679_EN_TXT.pdf"
EMBEDDING_DIMENSION = 1536


def fake_embed_with_failure(texts):
    """
    First two embedding batches succeed.
    Third batch fails.
    """
    fake_embed_with_failure.call_count += 1

    batch_number = fake_embed_with_failure.call_count

    print(
        f"  fake embedding call {batch_number}: "
        f"{len(texts)} chunks"
    )

    if batch_number == 3:
        raise RuntimeError("Simulated embedding service failure")

    return [
        [0.001 * (index + 1)] * EMBEDDING_DIMENSION
        for index, _ in enumerate(texts)
    ]


fake_embed_with_failure.call_count = 0


def fake_embed_successfully(texts):
    """
    Used during recovery.
    """
    fake_embed_successfully.call_count += 1

    print(
        f"  recovery embedding call "
        f"{fake_embed_successfully.call_count}: "
        f"{len(texts)} chunks"
    )

    return [
        [0.002 * (index + 1)] * EMBEDDING_DIMENSION
        for index, _ in enumerate(texts)
    ]


fake_embed_successfully.call_count = 0


def test_embedding_failure_and_recovery():
    db = SessionLocal()

    parsed_path = f"/tmp/test_embedding_failure_{uuid.uuid4()}.json"

    document = None
    document_version = None
    job = None

    try:
        # ---------------------------------------------------------
        # PARSE DOCUMENT
        # ---------------------------------------------------------

        parser = ParserFactory.get_parser("application/pdf")
        parsed = parser.parse(PDF_PATH)

        with open(parsed_path, "w", encoding="utf-8") as file:
            json.dump(document_to_dict(parsed), file)

        print()
        print("PARSED:")
        print("  pages:", parsed.page_count)
        print("  elements:", len(parsed.elements))

        # ---------------------------------------------------------
        # CREATE DB STATE
        # ---------------------------------------------------------

        document = Document(
            title="Embedding Failure Recovery Test GDPR",
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
            parsed_text_path=parsed_path,
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
            status=JobStatus.PROCESSING,
            progress=0,
            execution_id=str(uuid.uuid4()),
        )

        db.add(job)
        db.commit()

        context = {
            "document_version_id": str(document_version.id),
            "job_id": str(job.id),
            "execution_id": str(uuid.uuid4()),
        }

        # ---------------------------------------------------------
        # CREATE 180 CHUNKS
        # ---------------------------------------------------------

        print()
        print("========== CHUNK TASK ==========")

        chunk_result = chunk_document.run(context)

        assert chunk_result["chunk_count"] == 180

        db.expire_all()

        chunks = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id
            )
            .order_by(Chunk.chunk_index)
            .all()
        )

        assert len(chunks) == 180

        print("chunks:", len(chunks))

        # ---------------------------------------------------------
        # FAILURE TEST
        # ---------------------------------------------------------

        print()
        print("========== FAILURE TEST ==========")

        fake_embed_with_failure.call_count = 0

        with patch(
            "apps.worker.tasks.embedding_task.EmbeddingService"
        ) as mock_embedding_service:

            mock_embedding_service.return_value.embed.side_effect = (
                fake_embed_with_failure
            )

            try:
                embed_document.run(context)
                raise AssertionError(
                    "Expected embedding task to fail"
                )

            except RuntimeError as exc:
                assert str(exc) == (
                    "Simulated embedding service failure"
                )

                print("expected failure:", exc)

        # ---------------------------------------------------------
        # VERIFY PARTIAL PROGRESS
        # ---------------------------------------------------------

        db.expire_all()

        embedded_count = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id,
                Chunk.embedding.is_not(None),
            )
            .count()
        )

        missing_count = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id,
                Chunk.embedding.is_(None),
            )
            .count()
        )

        document_version = db.get(
            DocumentVersion,
            document_version.id,
        )

        job = db.get(
            IngestionJob,
            job.id,
        )

        print()
        print("========== AFTER FAILURE ==========")
        print("embedded:", embedded_count)
        print("missing:", missing_count)
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
            "error:",
            job.error_message,
        )

        assert embedded_count == 100
        assert missing_count == 80

        assert (
            document_version.processing_status
            == ProcessingStatus.FAILED
        )

        assert job.status == JobStatus.FAILED

        assert job.error_message == (
            "Simulated embedding service failure"
        )

        # ---------------------------------------------------------
        # RECOVERY
        # ---------------------------------------------------------

        print()
        print("========== RECOVERY ==========")

        fake_embed_successfully.call_count = 0

        with patch(
            "apps.worker.tasks.embedding_task.EmbeddingService"
        ) as mock_embedding_service:

            mock_embedding_service.return_value.embed.side_effect = (
                fake_embed_successfully
            )

            recovery_result = embed_document.run(context)

        print("recovery result:", recovery_result)

        assert recovery_result["embedded_count"] == 80
        assert recovery_result["status"] == (
            ProcessingStatus.READY.value
        )

        # ---------------------------------------------------------
        # VERIFY FINAL STATE
        # ---------------------------------------------------------

        db.expire_all()

        final_embedded_count = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id,
                Chunk.embedding.is_not(None),
            )
            .count()
        )

        final_missing_count = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id,
                Chunk.embedding.is_(None),
            )
            .count()
        )

        document_version = db.get(
            DocumentVersion,
            document_version.id,
        )

        job = db.get(
            IngestionJob,
            job.id,
        )

        print()
        print("========== FINAL STATE ==========")
        print(
            "embedded:",
            final_embedded_count,
        )
        print(
            "missing:",
            final_missing_count,
        )
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

        assert final_embedded_count == 180
        assert final_missing_count == 0

        assert (
            document_version.processing_status
            == ProcessingStatus.READY
        )

        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100

        # ---------------------------------------------------------
        # VERIFY RECOVERY ONLY PROCESSED MISSING CHUNKS
        # ---------------------------------------------------------

        assert fake_embed_successfully.call_count == 2

        print()
        print(
            "recovery embedding calls:",
            fake_embed_successfully.call_count,
        )

        print()
        print("========================================")
        print("EMBEDDING FAILURE + RECOVERY TEST PASSED")
        print("========================================")

    finally:
        if document_version:
            db.query(Chunk).filter(
                Chunk.document_version_id == document_version.id
            ).delete(
                synchronize_session=False
            )

        if job:
            db.delete(job)

        if document_version:
            db.delete(document_version)

        if document:
            db.delete(document)

        db.commit()
        db.close()

        if os.path.exists(parsed_path):
            os.remove(parsed_path)


if __name__ == "__main__":
    test_embedding_failure_and_recovery()
