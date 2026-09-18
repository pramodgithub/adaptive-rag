from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from enums.job_status import JobStatus
from enums.processing_status import ProcessingStatus


class IngestionResponse(BaseModel):
    execution_id: UUID
    document_id: UUID
    document_version_id: UUID
    status: JobStatus


class IngestionStatusResponse(BaseModel):
    execution_id: UUID
    document_id: UUID
    document_version_id: UUID
    job_status: JobStatus
    processing_status: ProcessingStatus
    progress: int
    retry_count: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
