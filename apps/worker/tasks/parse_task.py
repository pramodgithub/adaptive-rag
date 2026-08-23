from database.session import SessionLocal

from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob

from services.storage.file_storage import FileStorage
from services.ingestion.parsers.factory import ParserFactory

from apps.worker.celery_app import celery
from enums.job_status import JobStatus
from enums.processing_status import ProcessingStatus


@celery.task(
    name="ingestion.parse_document"
)
def parse_document(context):

    db = SessionLocal()
    storage = FileStorage()

    try:

        document_version = db.get(
            DocumentVersion,
            context["document_version_id"]
        )

        job = db.get(
            IngestionJob,
            context["job_id"]
        )

        if not document_version:
            raise ValueError(
                "Document version not found"
            )

        if not job:
            raise ValueError(
                "Ingestion job not found"
            )

        job.status = JobStatus.PROCESSING
        document_version.processing_status = ProcessingStatus.PROCESSING

        db.commit()

        parser = ParserFactory.get_parser(
            document_version.mime_type
        )

        parsed = parser.parse(
            document_version.storage_path
        )

        parsed_artifact = {
            "page_count": parsed.page_count,
            "pages": [
                {
                    "page_number": page.page_number,
                    "text": page.text
                }
                for page in parsed.pages
            ]
        }

        parsed_text_path = storage.save_json(
            parsed_artifact,
            document_version.file_name
        )

        document_version.parsed_text_path = (
            parsed_text_path
        )

        db.commit()

        return {
            **context,
            "parsed_text_path": parsed_text_path,
            "page_count": parsed.page_count
        }

    except Exception as exc:

        db.rollback()

        job = db.get(
            IngestionJob,
            context["job_id"]
        )

        if job:
            job.status = "FAILED"
            job.error_message = str(exc)

        document_version = db.get(
            DocumentVersion,
            context["document_version_id"]
        )

        if document_version:
            document_version.processing_status = "FAILED"

        db.commit()

        raise

    finally:
        db.close()
