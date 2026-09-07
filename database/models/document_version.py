import uuid

from sqlalchemy import String
from sqlalchemy import Column
from sqlalchemy import BigInteger, Integer, Boolean
from sqlalchemy import JSON
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import DateTime, Date, func
from sqlalchemy.dialects.postgresql import UUID
from enums.processing_status import ProcessingStatus
from sqlalchemy.orm import relationship
from database.models.base import Base
from sqlalchemy import UniqueConstraint


class DocumentVersion(Base):

    __tablename__ = "document_versions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False
    )

    version = Column(
        Integer,
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    storage_path = Column(
        String(500),
        nullable=False
    )

    checksum = Column(
        String(64),
        nullable=False
    )

    file_name = Column(
        String(255),
        nullable=False
    )

    parsed_text_path = Column(
        String(500),
        nullable=True
    )

    mime_type = Column(
        String(100)
    )

    file_size = Column(
        BigInteger
    )

    embedding_model = Column(
        String(100)
    )

    embedding_dimension = Column(
        Integer
    )

    processing_status = Column(
        Enum(ProcessingStatus, native_enum=False, validate_strings=True),
        default=ProcessingStatus.UPLOADING,
        nullable=False,
    )

    source_type = Column(
        String(100),
        nullable=True,
    )

    issuer = Column(
        String(255),
        nullable=True,
    )

    jurisdiction = Column(
        String(100),
        nullable=True,
    )

    authority_level = Column(
        String(50),
        nullable=True,
    )

    publication_date = Column(
        Date,
        nullable=True,
    )

    effective_date = Column(
        Date,
        nullable=True,
    )

    expiration_date = Column(
        Date,
        nullable=True,
    )

    verification_status = Column(
        String(50),
        nullable=True,
    )

    chunk_count = Column(
        Integer,
        default=0,
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    document = relationship(
        "Document",
        back_populates="versions",
        foreign_keys=[document_id]
    )

    chunks = relationship(
        "Chunk",
        back_populates="document_version",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index"
    )

    ingestion_jobs = relationship(
        "IngestionJob",
        back_populates="document_version",
        cascade="all, delete-orphan"
    )
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_version"),
    )
