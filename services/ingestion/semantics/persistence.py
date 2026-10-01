from sqlalchemy.orm import Session

from database.models.chunk import Chunk
from database.models.chunk_semantic_entity import ChunkSemanticEntity

from .models import SemanticEntity


class SemanticEntityPersistenceService:
    def save(
        self,
        db: Session,
        chunk: Chunk,
        entities: list[SemanticEntity],
    ) -> int:
        if not entities:
            return 0

        records = [
            ChunkSemanticEntity(
                chunk_id=chunk.id,
                framework=entity.framework,
                identifier=entity.identifier,
                entity_type=entity.entity_type.value,
                title=entity.title,
                parent_identifier=entity.parent_identifier,
                confidence=entity.confidence,
                validation_status=entity.validation_status.value,
                source=entity.source,
                metadata=entity.metadata,
            )
            for entity in entities
        ]

        db.add_all(records)
        db.flush()

        return len(records)
