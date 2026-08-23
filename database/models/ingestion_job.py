import uuid

from enums.job_status import JobStatus
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy import Index
from database.models.base import Base


class IngestionJob(Base):

    __tablename__ = "ingestion_jobs"

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

    status = Column(
        Enum(JobStatus, native_enum=False, validate_strings=True),
        default=JobStatus.PENDING,
        nullable=False
    )

    progress = Column(
        Integer,
        default=0,
        nullable=False
    )

    retry_count = Column(
        Integer,
        default=0,
        nullable=False
    )

    worker = Column(
        String(255)
    )

    error_message = Column(
        Text
    )

    execution_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.uuid4,

    )

    started_at = Column(
        DateTime(timezone=True)
    )

    completed_at = Column(
        DateTime(timezone=True)
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    document_version = relationship(
        "DocumentVersion",
        back_populates="ingestion_jobs"
    )


__table_args__ = (
    Index("idx_ingestion_job_version", "document_version_id"),
    Index("idx_ingestion_job_status", "status"),
    Index("idx_ingestion_execution_id", "execution_id")
)
