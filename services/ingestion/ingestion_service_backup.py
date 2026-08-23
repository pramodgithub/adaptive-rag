# import uuid
# from database.models import document_version
# from database.session import SessionLocal
# from database.models.document import Document
# from database.models.chunk import Chunk
# from services.ingestion.chunk_service import ChunkService
# from core.embeddings.embedding_service import EmbeddingService


# class IngestionService:
#     def __init__(self):
#         self.chunk_service = ChunkService()
#         self.embedding_service = EmbeddingService()

#     def ingest(self, text: str, filename: str):
#         db = SessionLocal()
#         try:
#             # Create and save document
#             document = Document(
#                 title=filename,
#                 source="upload",
#                 doc_metadata=""
#             )
#             db.add(document)
#             db.flush()

#             # Process chunks and embeddings
#             chunks = self.chunk_service.split(text)
#             for chunk in chunks:
#                 embedding = self.embedding_service.embed(chunk)

#                 chunk_record = Chunk(
#                     document_version_id=document_version.id,
#                     chunk_index=chunks.index(chunk),
#                     text=chunk,
#                     embedding=embedding
#                 )
#                 db.add(chunk_record)

#             db.commit()

#             return {
#                 "document_id": str(document.id),
#                 "chunks": len(chunks)
#             }
#         finally:
#             db.close()
