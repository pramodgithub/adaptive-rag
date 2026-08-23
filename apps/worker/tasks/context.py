from dataclasses import dataclass
from uuid import UUID


@dataclass
class IngestionContext:
    execution_id: UUID
    document_id: UUID
    document_version_id: UUID
    job_id: UUID
    storage_path: str
