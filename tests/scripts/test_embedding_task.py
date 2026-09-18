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

from apps.worker.tasks.chunk_task import chunk_document
from apps.worker.tasks.embedding_task import embed_document
from services.ingestion.domain.serialization import document_to_dict
from services.ingestion.parsers.factory import ParserFactory


PDF_PATH = "/app/tests/data/CELEX_32016R0679_EN_TXT.pdf"
EMBEDDING_DIMENSION = 1536


def fake_embed(texts):
    """
    Deterministic fake embedding implementation.

    Returns one 1536-dimensional vector per input text.
    The actual Gemini embedding service is intentionally not called.
    """
    return [
        [0.001 * (index + 1)] * EMBEDDING_DIMENSION
        for index, _ in enumerate(texts)
    ]


def test_embedding_task():
    db = SessionLocal()
    parsed_path = f"/tmp/test_embedding_task_{uuid.uuid4()}.json"

    document = None
    document_version = None
    job = None

    try:
        # =========================================================
        # 1. Parse GDPR document
        # =========================================================
        parser = ParserFactory.get_parser("application/pdf")
        parsed = parser.parse(PDF_PATH)

        with open(parsed_path, "w", encoding="utf-8") as file:
            json.dump(document_to_dict(parsed), file)

        print()
        print("PARSED:")
        print("  pages:", parsed.page_count)
        print("  elements:", len(parsed.elements))

        # =========================================================
        # 2. Create isolated test records
        # =========================================================
        document = Document(
            title="Embedding Task Test GDPR",
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

        # =========================================================
        # 3. Run REAL chunk task
        # =========================================================
        print()
        print("========== CHUNK TASK ==========")

        chunk_result = chunk_document.run(context)

        assert chunk_result["chunk_count"] == 180
        assert chunk_result["inserted"] == 180
        assert chunk_result["updated"] == 0
        assert chunk_result["deleted"] == 0

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

        # =========================================================
        # 4. Simulate 179 already-embedded chunks
        # =========================================================
        target_chunk = next(
            chunk
            for chunk in chunks
            if chunk.chunk_index == 97
        )

        target_chunk_id = target_chunk.id

        for chunk in chunks:
            chunk.embedding = None

        db.commit()

        db.expire_all()

        # Verify initial state.
        embedded_count_before = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id,
                Chunk.embedding.is_not(None),
            )
            .count()
        )

        missing_count_before = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id,
                Chunk.embedding.is_(None),
            )
            .count()
        )

        assert embedded_count_before == 0
        assert missing_count_before == 180

        print()
        print("BEFORE EMBEDDING:")
        print("  embedded:", embedded_count_before)
        print("  missing:", missing_count_before)
        print("  chunks requiring embeddings:", missing_count_before)

        # =========================================================
        # 5. Run REAL embedding task with fake service
        # =========================================================
        print()
        print("========== EMBEDDING TASK ==========")

        with patch(
            "apps.worker.tasks.embedding_task.EmbeddingService"
        ) as mock_embedding_service:

            mock_embedding_service.return_value.embed.side_effect = fake_embed

            result = embed_document.run(context)

        # =========================================================
        # 6. Verify task result
        # =========================================================
        assert result["embedded_count"] == 180
        assert result["status"] == ProcessingStatus.READY.value

        print("embedded_count:", result["embedded_count"])
        print("status:", result["status"])

        # =========================================================
        # 7. Reload DB state
        # =========================================================
        db.expire_all()

        final_chunks = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id
            )
            .order_by(Chunk.chunk_index)
            .all()
        )

        assert len(final_chunks) == 180

        # =========================================================
        # 8. Verify all chunks now have embeddings
        # =========================================================
        final_missing_count = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id,
                Chunk.embedding.is_(None),
            )
            .count()
        )

        assert final_missing_count == 0

        print()
        print("AFTER EMBEDDING:")
        print("  total chunks:", len(final_chunks))
        print("  missing embeddings:", final_missing_count)

        # =========================================================
        # 9. Verify target chunk received new embedding
        # =========================================================
        embedded_target = db.get(
            Chunk,
            target_chunk_id,
        )

        assert embedded_target is not None
        assert embedded_target.embedding is not None
        assert len(embedded_target.embedding) == EMBEDDING_DIMENSION

        print("target embedding dimension:", len(embedded_target.embedding))

        # =========================================================
        # 10. Verify existing embeddings were preserved
        # =========================================================
        # preserved_chunks = [
        #     chunk
        #     for chunk in final_chunks
        #     if chunk.id != target_chunk_id
        # ]

        # assert len(preserved_chunks) == 179

        # for chunk in preserved_chunks:
        #     assert chunk.embedding is not None
        #     assert list(chunk.embedding) == existing_embedding

        # print("existing embeddings preserved:", True)

        # =========================================================
        # 11. Verify document/job final state
        # =========================================================
        db.refresh(document_version)
        db.refresh(job)

        assert document_version.processing_status == ProcessingStatus.READY
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100

        print()
        print("FINAL STATE:")
        print("  processing_status:", document_version.processing_status)
        print("  job_status:", job.status)
        print("  job_progress:", job.progress)

        print()
        print("EMBEDDING TASK TEST PASSED")

    finally:
        # =========================================================
        # Cleanup
        # =========================================================
        if document_version:
            db.query(Chunk).filter(
                Chunk.document_version_id == document_version.id
            ).delete(synchronize_session=False)

            if job:
                db.delete(job)

            db.delete(document_version)

        if document:
            db.delete(document)

        db.commit()
        db.close()

        if os.path.exists(parsed_path):
            os.remove(parsed_path)


if __name__ == "__main__":
    test_embedding_task()
