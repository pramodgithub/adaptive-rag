import uuid

from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID

from database.models.base import Base


class AuditLog(Base):

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    query = Column(Text)

    final_query = Column(Text)

    answer = Column(Text)

    confidence = Column(Float)

    retry_count = Column(Integer)

    model = Column(String)

    provider = Column(String)

    latency_ms = Column(Integer)

    total_tokens = Column(Integer)

    sources = Column(JSON)
