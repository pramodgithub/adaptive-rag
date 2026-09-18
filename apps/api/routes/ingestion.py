from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile

from database.models.document import Document
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob
from database.session import SessionLocal
from services.ingestion.ingestion_service import IngestionService

from apps.api.schemas.ingestion import (
    IngestionResponse,
    IngestionStatusResponse,
)

router = APIRouter(
    prefix="/api/v1/ingestions",
    tags=["ingestion"],
)

ingestion_service = IngestionService()


@router.post(
    "",
    response_model=IngestionResponse,
    status_code=202,
)
async def create_ingestion(
    file: UploadFile = File(...),
):
    return await ingestion_service.create_ingestion(file)


@router.get(
    "/{execution_id}",
    response_model=IngestionStatusResponse,
)
def get_ingestion_status(
    execution_id: UUID,
):
    db = SessionLocal()

    try:
        job = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.execution_id == execution_id
            )
            .first()
        )

        if not job:
            raise HTTPException(
                status_code=404,
                detail="Ingestion execution not found",
            )

        document_version = db.get(
            DocumentVersion,
            job.document_version_id,
        )

        if not document_version:
            raise HTTPException(
                status_code=404,
                detail="Document version not found",
            )

        return IngestionStatusResponse(
            execution_id=job.execution_id,
            document_id=document_version.document_id,
            document_version_id=document_version.id,
            job_status=job.status,
            processing_status=document_version.processing_status,
            progress=job.progress,
            retry_count=job.retry_count,
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    finally:
        db.close()
