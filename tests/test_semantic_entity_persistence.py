import uuid

from database.models.chunk import Chunk
from database.models.document import Document
from database.models.document_version import DocumentVersion
from database.models.chunk_semantic_entity import ChunkSemanticEntity
from database.session import SessionLocal
from services.ingestion.semantics.models import (
    SemanticEntity,
    SemanticEntityType,
    SemanticValidationStatus,
)
from services.ingestion.semantics.persistence import (
    SemanticEntityPersistenceService,
)


def test_semantic_entity_persistence():
    db = SessionLocal()
    document = None

    try:
        # ---------------------------------------------------------
        # 1. Create temporary Document
        # ---------------------------------------------------------
        document = Document(
            title=f"TEST Semantic Entities {uuid.uuid4()}",
            source="test",
            document_type="compliance",
        )

        db.add(document)
        db.flush()

        # ---------------------------------------------------------
        # 2. Create DocumentVersion
        # ---------------------------------------------------------
        document_version = DocumentVersion(
            document_id=document.id,
            version=1,
            is_active=True,
            storage_path="test",
            checksum=str(uuid.uuid4()),
            file_name="semantic-test.pdf",
            mime_type="application/pdf",
            file_size=0,
            embedding_model="test",
            embedding_dimension=3072,
            chunk_count=1,
        )

        db.add(document_version)
        db.flush()

        # ---------------------------------------------------------
        # 3. Create one chunk containing multiple controls
        # ---------------------------------------------------------
        chunk = Chunk(
            document_version_id=document_version.id,
            chunk_index=0,
            page_number=44,
            page_start=44,
            page_end=44,
            text=(
                "CC6.1.4 Access reviews are performed.\n\n"
                "CC6.1.5 Access is reviewed periodically.\n\n"
                "CC6.1.6 Access exceptions are documented."
            ),
            section_path=["Logical Access"],
            structure_type=None,
            identifier=None,
            parent_identifier=None,
            element_indexes=[10],
            chunk_metadata={"source": "test"},
        )

        db.add(chunk)
        db.flush()

        # ---------------------------------------------------------
        # 4. Build semantic entities
        # ---------------------------------------------------------
        entities = [
            SemanticEntity(
                framework="soc2",
                identifier="CC6.1.4",
                entity_type=SemanticEntityType.CONTROL,
                title="Access reviews are performed",
                parent_identifier="CC6.1",
                confidence=0.96,
                validation_status=SemanticValidationStatus.ACCEPTED,
                source="llm",
            ),
            SemanticEntity(
                framework="soc2",
                identifier="CC6.1.5",
                entity_type=SemanticEntityType.CONTROL,
                title="Access is reviewed periodically",
                parent_identifier="CC6.1",
                confidence=0.94,
                validation_status=SemanticValidationStatus.ACCEPTED,
                source="llm",
            ),
            SemanticEntity(
                framework="soc2",
                identifier="CC6.1.6",
                entity_type=SemanticEntityType.CONTROL,
                title="Access exceptions are documented",
                parent_identifier="CC6.1",
                confidence=0.91,
                validation_status=SemanticValidationStatus.REVIEW,
                source="llm",
            ),
        ]

        # ---------------------------------------------------------
        # 5. Persist semantic entities
        # ---------------------------------------------------------
        service = SemanticEntityPersistenceService()

        saved_count = service.save(
            db=db,
            chunk=chunk,
            entities=entities,
        )

        assert saved_count == 3

        db.commit()

        # ---------------------------------------------------------
        # 6. Read entities back from PostgreSQL
        # ---------------------------------------------------------
        stored_entities = (
            db.query(ChunkSemanticEntity)
            .filter(
                ChunkSemanticEntity.chunk_id == chunk.id
            )
            .order_by(ChunkSemanticEntity.identifier)
            .all()
        )

        assert len(stored_entities) == 3

        # ---------------------------------------------------------
        # 7. Validate identifiers
        # ---------------------------------------------------------
        identifiers = [
            entity.identifier
            for entity in stored_entities
        ]

        assert identifiers == [
            "CC6.1.4",
            "CC6.1.5",
            "CC6.1.6",
        ]

        # ---------------------------------------------------------
        # 8. Validate framework and entity type
        # ---------------------------------------------------------
        assert all(
            entity.framework == "soc2"
            for entity in stored_entities
        )

        assert all(
            entity.entity_type == "control"
            for entity in stored_entities
        )

        # ---------------------------------------------------------
        # 9. Validate parent relationships
        # ---------------------------------------------------------
        assert all(
            entity.parent_identifier == "CC6.1"
            for entity in stored_entities
        )

        # ---------------------------------------------------------
        # 10. Validate confidence and validation status
        # ---------------------------------------------------------
        assert stored_entities[0].confidence == 0.96
        assert stored_entities[0].validation_status == "accepted"

        assert stored_entities[2].confidence == 0.91
        assert stored_entities[2].validation_status == "review"

        print("\nSemantic entities persisted successfully:")

        for entity in stored_entities:
            print(
                f"  {entity.identifier}"
                f" | framework={entity.framework}"
                f" | type={entity.entity_type}"
                f" | parent={entity.parent_identifier}"
                f" | confidence={entity.confidence}"
                f" | status={entity.validation_status}"
            )

        print("\nSEMANTIC ENTITY PERSISTENCE TEST PASSED")

    finally:
        db.rollback()

        # ---------------------------------------------------------
        # 11. Cleanup
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
                    db.query(ChunkSemanticEntity).filter(
                        ChunkSemanticEntity.chunk_id.in_(
                            db.query(Chunk.id).filter(
                                Chunk.document_version_id == version.id
                            )
                        )
                    ).delete(synchronize_session=False)

                    db.query(Chunk).filter(
                        Chunk.document_version_id == version.id
                    ).delete(synchronize_session=False)

                    db.delete(version)

                db.delete(existing_document)
                db.commit()

        db.close()


if __name__ == "__main__":
    test_semantic_entity_persistence()
