from database.models.audit import AuditLog
from database.models.base import Base
from database.models.chunk import Chunk
from database.models.document import Document
from database.session import engine


def init():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init()
    print("Database initialized")
