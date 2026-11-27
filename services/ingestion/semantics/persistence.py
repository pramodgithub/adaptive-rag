from sqlalchemy.orm import Session

from database.models.chunk import Chunk
from database.models.chunk_semantic_entity import ChunkSemanticEntity

from .models import SemanticEntity


class SemanticEntityPersistenceService:
    def save(self, db: Session, chunk: Chunk, entities: list[SemanticEntity]) -> int:
        if not entities:
            return 0

        # The same id can come up twice in one chunk (definition and mention).
        # Keep the one with the highest confidence, so one chunk can't fail
        # the whole document.
        best: dict[tuple[str, str, str], SemanticEntity] = {}
        for entity in entities:
            key = (entity.framework, entity.entity_type.value, entity.identifier)
            if key not in best or entity.confidence > best[key].confidence:
                best[key] = entity

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
                entity_metadata=entity.metadata,
            )
            for entity in best.values()
        ]

        db.add_all(records)
        db.flush()
        return len(records)
