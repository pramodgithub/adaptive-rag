
import uuid

from enums.document_status import DocumentStatus
from sqlalchemy import String
from sqlalchemy import Column
from sqlalchemy import JSON
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import DateTime
from database.models.base import Base
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from sqlalchemy import Enum


class Document(Base):

    __tablename__ = "documents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    title = Column(
        String(500),
        nullable=False
    )

    source = Column(
        String(255),
        nullable=False
    )

    document_type = Column(
        String(100),
        nullable=False,
        default="general"
    )

    owner = Column(
        String(255)
    )

    status = Column(
        Enum(DocumentStatus, native_enum=False, validate_strings=True),
        default=DocumentStatus.ACTIVE,
        nullable=False,
    )

    active_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", use_alter=True,
                   name="fk_document_active_version"),
        nullable=True
    )

    doc_metadata = Column("metadata", JSON)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    deleted_at = Column(
        DateTime(timezone=True)
    )

    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version"
    )
