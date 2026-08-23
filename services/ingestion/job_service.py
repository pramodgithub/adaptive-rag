import uuid

from sqlalchemy.orm import Session

from database.models.ingestion_job import IngestionJob


class IngestionJobService:

    def create(
        self,
        db: Session,
        document_version_id: uuid.UUID,
        execution_id: uuid.UUID
    ) -> IngestionJob:

        job = IngestionJob(
            document_version_id=document_version_id,
            execution_id=execution_id,
            status="PENDING",
            progress=0,
            retry_count=0
        )

        db.add(job)
        db.flush()

        return job
