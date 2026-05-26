import uuid
from sqlalchemy import String
from sqlalchemy import Column
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID
from database.models.base import Base


class Document(Base):
    __tablename__ = "documents"
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    title = Column(String)
    source = Column(String)
    doc_metadata = Column("metadata", Text)
