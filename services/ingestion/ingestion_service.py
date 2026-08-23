import hashlib

from fastapi import UploadFile
from sqlalchemy.orm import Session

from database.session import SessionLocal
from services.storage.file_storage import FileStorage
from apps.worker.tasks.pipeline import start_ingestion

from database.models.document import Document
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob


class IngestionService:

    def __init__(self):
        self.storage = FileStorage()

    async def create_ingestion(
        self,
        file: UploadFile
    ):
        content = await file.read()

        checksum = hashlib.sha256(content).hexdigest()

        storage_path = self.storage.save(
            content,
            file.filename
        )

        db: Session = SessionLocal()

        try:
            document = Document(
                title=file.filename,
                source="upload",
                document_type="general"
            )

            db.add(document)
            db.flush()

            document_version = DocumentVersion(
                document_id=document.id,
                version=1,
                is_active=True,
                storage_path=storage_path,
                checksum=checksum,
                file_name=file.filename,
                mime_type=file.content_type,
                file_size=len(content)
            )

            db.add(document_version)
            db.flush()

            document.active_version_id = document_version.id

            job = IngestionJob(
                document_version_id=document_version.id
            )

            db.add(job)
            db.flush()

            context = {
                "execution_id": str(job.execution_id),
                "document_id": str(document.id),
                "document_version_id": str(document_version.id),
                "job_id": str(job.id),
                "storage_path": storage_path
            }

            # Database transaction must be committed before
            # the worker starts processing.
            db.commit()

            # Send the task to Celery.
            start_ingestion.delay(context)

            return {
                "document_id": str(document.id),
                "document_version_id": str(document_version.id),
                "job_id": str(job.id),
                "execution_id": str(job.execution_id),
                "status": "QUEUED"
            }

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()
