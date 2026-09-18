import json
import os
import uuid

from database.models.chunk import Chunk
from database.models.document import Document
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob
from database.session import SessionLocal

from enums.job_status import JobStatus

from apps.worker.tasks.chunk_task import chunk_document
from services.ingestion.domain.serialization import document_to_dict
from services.ingestion.parsers.factory import ParserFactory


PDF_PATH = "/app/tests/data/CELEX_32016R0679_EN_TXT.pdf"
EMBEDDING_DIMENSION = 1536


def test_chunk_task_embedding_invalidation():
    db = SessionLocal()
    parsed_path = f"/tmp/test_chunk_task_{uuid.uuid4()}.json"

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
            title="Chunk Task Embedding Test GDPR",
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
        # 3. FIRST RUN
        # =========================================================
        print()
        print("========== FIRST RUN ==========")

        result = chunk_document.run(context)

        assert result["chunk_count"] == 180
        assert result["inserted"] == 180
        assert result["updated"] == 0
        assert result["deleted"] == 0

        first_chunks = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id
            )
            .order_by(Chunk.chunk_index)
            .all()
        )

        assert len(first_chunks) == 180

        print("chunks:", len(first_chunks))

        # =========================================================
        # 4. Select Article 32 chunk
        # =========================================================
        target_chunk = next(
            chunk
            for chunk in first_chunks
            if chunk.chunk_index == 97
        )

        original_chunk_id = target_chunk.id
        original_text = target_chunk.text

        assert target_chunk.identifier == "32"
        assert target_chunk.structure_type == "article"
        assert target_chunk.section_path == ["Article 32"]

        print("target chunk:")
        print("  index:", target_chunk.chunk_index)
        print("  id:", target_chunk.id)
        print("  identifier:", target_chunk.identifier)

        # =========================================================
        # 5. Simulate an existing valid embedding
        # =========================================================
        fake_embedding = [0.123] * EMBEDDING_DIMENSION

        target_chunk.embedding = fake_embedding
        db.commit()

        db.expire_all()

        embedded_chunk = db.get(
            Chunk,
            original_chunk_id,
        )

        assert embedded_chunk is not None
        assert embedded_chunk.embedding is not None

        print("embedding created:")
        print("  dimension:", len(embedded_chunk.embedding))

        # =========================================================
        # 6. SECOND RUN - unchanged content
        # =========================================================
        print()
        print("========== SECOND RUN ==========")
        print("Testing unchanged content preserves embedding")

        result = chunk_document.run(context)

        assert result["chunk_count"] == 180
        assert result["inserted"] == 0
        assert result["updated"] == 180
        assert result["deleted"] == 0

        db.expire_all()

        unchanged_chunk = db.get(
            Chunk,
            original_chunk_id,
        )

        assert unchanged_chunk is not None
        assert unchanged_chunk.id == original_chunk_id
        assert unchanged_chunk.text == original_text
        assert unchanged_chunk.embedding is not None

        print("same chunk ID:", unchanged_chunk.id == original_chunk_id)
        print("text unchanged:", unchanged_chunk.text == original_text)
        print("embedding preserved:", unchanged_chunk.embedding is not None)

        # =========================================================
        # 7. Modify the persisted chunk text
        # =========================================================
        print()
        print("========== MODIFY CHUNK ==========")

        unchanged_chunk.text = "INTENTIONALLY MODIFIED TEST TEXT"
        db.commit()

        db.expire_all()

        modified_chunk = db.get(
            Chunk,
            original_chunk_id,
        )

        assert modified_chunk is not None
        assert modified_chunk.text == "INTENTIONALLY MODIFIED TEST TEXT"
        assert modified_chunk.embedding is not None

        print("chunk modified successfully")
        print("  text changed:", True)
        print("  old embedding still present:", True)

        # =========================================================
        # 8. THIRD RUN - changed content
        # =========================================================
        print()
        print("========== THIRD RUN ==========")
        print("Testing changed content invalidates embedding")

        result = chunk_document.run(context)

        assert result["chunk_count"] == 180
        assert result["inserted"] == 0
        assert result["updated"] == 180
        assert result["deleted"] == 0

        # Important because chunk_document uses a separate session.
        db.expire_all()

        reconciled_chunk = db.get(
            Chunk,
            original_chunk_id,
        )

        assert reconciled_chunk is not None

        # Same DB row must remain.
        assert reconciled_chunk.id == original_chunk_id

        # Original generated content must be restored.
        assert reconciled_chunk.text == original_text

        # Because the persisted content was changed before
        # reconciliation, the old embedding must be invalidated.
        assert reconciled_chunk.embedding is None

        print("same chunk ID:", reconciled_chunk.id == original_chunk_id)
        print("original text restored:", reconciled_chunk.text == original_text)
        print("embedding invalidated:", reconciled_chunk.embedding is None)

        # =========================================================
        # 9. Verify final state
        # =========================================================
        final_chunks = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id
            )
            .all()
        )

        assert len(final_chunks) == 180

        chunk_indexes = [
            chunk.chunk_index
            for chunk in final_chunks
        ]

        assert len(chunk_indexes) == len(set(chunk_indexes))

        db.refresh(document_version)
        db.refresh(job)

        assert document_version.chunk_count == 180
        assert job.status == JobStatus.EMBEDDING
        assert job.progress == 50

        print()
        print("FINAL STATE:")
        print("  chunk_count:", document_version.chunk_count)
        print("  duplicate indexes:", False)
        print("  job_status:", job.status)
        print("  job_progress:", job.progress)

        print()
        print("CHUNK TASK EMBEDDING INVALIDATION TEST PASSED")

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
    test_chunk_task_embedding_invalidation()
