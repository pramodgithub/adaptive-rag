from sqlalchemy.orm import Session

from database.models.chunk import Chunk


class ChunkPersistenceService:

    def save(
        self,
        db: Session,
        document_version_id,
        chunks: list[dict]
    ):

        records = [
            Chunk(
                document_version_id=document_version_id,
                chunk_index=chunk["chunk_index"],
                page_number=chunk["page_number"],
                text=chunk["text"],
                embedding=chunk["embedding"]
            )
            for chunk in chunks
        ]

        db.add_all(records)
        db.flush()

        return len(records)
