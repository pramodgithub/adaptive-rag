import uuid

from sqlalchemy import Column
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID

from pgvector.sqlalchemy import Vector

from database.models.base import Base


class Chunk(Base):

    __tablename__ = "chunks"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    document_id = Column(
        UUID(as_uuid=True)
    )

    text = Column(
        Text
    )

    embedding = Column(
        Vector(3072)
    )
