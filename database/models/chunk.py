import uuid

from sqlalchemy import Column
from sqlalchemy import Text
from sqlalchemy import Integer
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from pgvector.sqlalchemy import Vector
from config.constants import EMBEDDING_DIMENSION

from database.models.base import Base


class Chunk(Base):

    __tablename__ = "chunks"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    document_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False
    )

    chunk_index = Column(
        Integer,
        nullable=False
    )

    page_number = Column(
        Integer,
        nullable=True
    )

    text = Column(
        Text,
        nullable=False
    )

    embedding = Column(
        Vector(EMBEDDING_DIMENSION),
        nullable=False
    )

    document_version = relationship(
        "DocumentVersion",
        back_populates="chunks"
    )

    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "chunk_index",
            name="uq_chunk_version_index"
        ),
        Index(
            "idx_chunk_version_page",
            "document_version_id", "page_number"
        ),
        Index(
            "idx_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )
