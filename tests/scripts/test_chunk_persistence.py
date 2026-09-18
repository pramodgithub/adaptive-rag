import os
import uuid

from database.models.chunk import Chunk
from database.models.document import Document
from database.models.document_version import DocumentVersion
from database.session import SessionLocal
from services.ingestion.chunking.chunker import ComplianceChunker
from services.ingestion.parsers.factory import ParserFactory
from services.ingestion.structure.structure_inference import StructureInferenceService


PDF_PATH = "/app/tests/data/CELEX_32016R0679_EN_TXT.pdf"


def test_gdpr_chunk_persistence():
    db = SessionLocal()

    document = None

    try:
        # ---------------------------------------------------------
        # 1. Parse GDPR document
        # ---------------------------------------------------------
        parser = ParserFactory.get_parser("application/pdf")
        parsed = parser.parse(PDF_PATH)

        print(f"Parsed document: {parsed.title}")
        print(f"Pages: {parsed.page_count}")
        print(f"Elements: {len(parsed.elements)}")

        # ---------------------------------------------------------
        # 2. Infer compliance structure
        # ---------------------------------------------------------
        structure_service = StructureInferenceService()
        structured_document = structure_service.infer(parsed)

        # ---------------------------------------------------------
        # 3. Build compliance chunks
        # ---------------------------------------------------------
        chunker = ComplianceChunker()
        chunks = chunker.chunk(structured_document)

        print(f"Generated chunks: {len(chunks)}")

        assert chunks
        assert any(
            chunk.structure_type == "article"
            and chunk.identifier == "32"
            for chunk in chunks
        ), "Article 32 chunk not found"

        # ---------------------------------------------------------
        # 4. Create temporary Document
        # ---------------------------------------------------------
        document = Document(
            title=f"TEST GDPR {uuid.uuid4()}",
            source="test",
            document_type="regulation",
        )

        db.add(document)
        db.flush()

        # ---------------------------------------------------------
        # 5. Create DocumentVersion
        # ---------------------------------------------------------
        document_version = DocumentVersion(
            document_id=document.id,
            version=1,
            is_active=True,
            storage_path=PDF_PATH,
            checksum=str(uuid.uuid4()),
            file_name=os.path.basename(PDF_PATH),
            mime_type="application/pdf",
            file_size=os.path.getsize(PDF_PATH),
            embedding_model="test",
            embedding_dimension=1536,
            chunk_count=len(chunks),
        )

        db.add(document_version)
        db.flush()

        # ---------------------------------------------------------
        # 6. Persist chunks
        # ---------------------------------------------------------
        persisted_chunks = []

        for chunk in chunks:
            db_chunk = Chunk(
                document_version_id=document_version.id,
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

            db.add(db_chunk)
            persisted_chunks.append(db_chunk)

        document_version.chunk_count = len(persisted_chunks)

        db.commit()

        print(f"Persisted chunks: {len(persisted_chunks)}")

        # ---------------------------------------------------------
        # 7. Read chunks back from PostgreSQL
        # ---------------------------------------------------------
        stored_chunks = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id
            )
            .order_by(Chunk.chunk_index)
            .all()
        )

        print(f"Read back chunks: {len(stored_chunks)}")

        assert len(stored_chunks) == len(chunks)

        # ---------------------------------------------------------
        # 8. Validate Article 32 persistence
        # ---------------------------------------------------------
        article_32 = next(
            (
                chunk
                for chunk in stored_chunks
                if chunk.structure_type == "article"
                and chunk.identifier == "32"
            ),
            None,
        )

        assert article_32 is not None, "Article 32 was not persisted"

        print("\nArticle 32 persisted successfully:")
        print(f"  chunk_index: {article_32.chunk_index}")
        print(f"  identifier: {article_32.identifier}")
        print(f"  structure_type: {article_32.structure_type}")
        print(f"  section_path: {article_32.section_path}")
        print(f"  page_start: {article_32.page_start}")
        print(f"  page_end: {article_32.page_end}")
        print(f"  element_indexes: {article_32.element_indexes}")
        print(f"  metadata: {article_32.chunk_metadata}")

        # ---------------------------------------------------------
        # 9. Validate semantic fields
        # ---------------------------------------------------------
        assert article_32.section_path == ["Article 32"]
        assert article_32.identifier == "32"
        assert article_32.structure_type == "article"
        assert article_32.page_start is not None
        assert article_32.page_end is not None
        assert article_32.element_indexes
        assert article_32.text

        print("\nGDPR CHUNK PERSISTENCE TEST PASSED")

    finally:
        db.rollback()

        # ---------------------------------------------------------
        # 10. Cleanup
        # ---------------------------------------------------------

        if document is not None:
            existing_document = (
                db.query(Document)
                .filter(Document.id == document.id)
                .first()
            )

            if existing_document:
                versions = (
                    db.query(DocumentVersion)
                    .filter(
                        DocumentVersion.document_id == existing_document.id
                    )
                    .all()
                )

                for version in versions:
                    db.query(Chunk).filter(
                        Chunk.document_version_id == version.id
                    ).delete(synchronize_session=False)

                for version in versions:
                    db.delete(version)

                db.delete(existing_document)
                db.commit()

        db.close()


if __name__ == "__main__":
    test_gdpr_chunk_persistence()
