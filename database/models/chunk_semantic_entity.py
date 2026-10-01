import uuid

from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models.base import Base


class ChunkSemanticEntity(Base):
    __tablename__ = "chunk_semantic_entities"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
    )

    framework = Column(
        String(100),
        nullable=False,
    )

    identifier = Column(
        String(100),
        nullable=False,
    )

    entity_type = Column(
        String(100),
        nullable=False,
    )

    title = Column(
        Text,
        nullable=True,
    )

    parent_identifier = Column(
        String(100),
        nullable=True,
    )

    confidence = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    validation_status = Column(
        String(50),
        nullable=False,
        default="review",
    )

    source = Column(
        String(50),
        nullable=False,
        default="llm",
    )

    entity_metadata = Column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    chunk = relationship(
        "Chunk",
        back_populates="semantic_entities",
    )

    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "framework",
            "identifier",
            name="uq_semantic_entity_chunk_identifier",
        ),
        Index(
            "idx_semantic_entity_chunk",
            "chunk_id",
        ),
        Index(
            "idx_semantic_entity_framework_identifier",
            "framework",
            "identifier",
        ),
        Index(
            "idx_semantic_entity_validation_status",
            "validation_status",
        ),
    )
