import os
from collections import Counter
import uuid
from unittest.mock import patch

from apps.worker.tasks.chunk_task import chunk_document
from database.models.chunk import Chunk
from database.models.document import Document
from database.models.document_version import DocumentVersion
from database.models.ingestion_job import IngestionJob
from database.session import SessionLocal

from enums.job_status import JobStatus
from enums.processing_status import ProcessingStatus

from apps.worker.celery_app import celery
from apps.worker.tasks.pipeline import start_ingestion
from services.retrieval.retrieval_service import RetrievalService


PDF_PATH = "/app/tests/data/CELEX_32016R0679_EN_TXT.pdf"
EMBEDDING_DIMENSION = 1536
EXPECTED_CHUNK_COUNT = 320


def fake_embed(texts):
    return [
        [0.001 * (index + 1)] * EMBEDDING_DIMENSION
        for index, _ in enumerate(texts)
    ]


def test_ingestion_lifecycle():
    db = SessionLocal()

    document = None
    document_version = None
    job = None

    try:

        # ---------------------------------------------------------
        # 21. RETRIEVAL REGRESSION
        # ---------------------------------------------------------

        retrieval_service = RetrievalService()

        retrieval_queries = [
            {
                "query": "CC6.1.4",
                "keywords": [
                    "CC6.1.4"
                ],
            },
            {
                "query": "What requirements are related to CC6.1.4?",
                "keywords": [
                    "CC6.1.4",
                    "related",
                    "requirements"
                ],
            },
        ]

        print()
        print("========== RETRIEVAL REGRESSION ==========")

        for test_case in retrieval_queries:
            query = test_case["query"]
            keywords = test_case["keywords"]

            results = retrieval_service.search(
                query,
                top_k=5,
            )

            print()
            print("Query:", query)
            print("Results:", len(results))

            assert results
            assert len(results) <= 5

            for index, result in enumerate(results):
                print(
                    f"  [{index}] "
                    f"score={result.score:.4f} "
                    f"chunk={result.chunk_index} "
                    f"page={result.page_number}"
                )

            retrieved_text = " ".join(
                result.text.lower()
                for result in results
            )

            matched_keywords = [
                keyword
                for keyword in keywords
                if keyword.lower() in retrieved_text
            ]

            assert matched_keywords, (
                f"No expected evidence found for query: {query}"
            )

            print("\n========== ADAPTIVE RETRIEVAL ==========")
            print(f"Query: {query}")
            print(f"Strategies: {result['strategies']}")
            print(f"All results: {len(result['all_results'])}")
            print(f"Retrieved: {len(result['retrieved'])}")

            for i, r in enumerate(result["retrieved"]):
                print(
                    f"  [{i}] "
                    f"source={r.source} "
                    f"score={r.score:.4f} "
                    f"chunk={r.chunk_index} "
                    f"page={r.page_number}"
                )

            counts = Counter(r.chunk_id for r in result["all_results"])
            duplicates = {
                str(chunk_id): count
                for chunk_id, count in counts.items()
                if count > 1
            }

            print(f"Duplicate chunks: {duplicates}")

    finally:
        # ---------------------------------------------------------
        # CLEANUP
        # ---------------------------------------------------------
        if document_version:
            db.query(Chunk).filter(
                Chunk.document_version_id == document_version.id
            ).delete(
                synchronize_session=False
            )

        if job:
            db.delete(job)

        # Document currently references this version through
        # active_version_id, so clear the FK before deleting it.
        if document:
            document.active_version_id = None
            db.flush()

        if document_version:
            db.delete(document_version)

        if document:
            db.delete(document)

        db.commit()
        db.close()


if __name__ == "__main__":
    test_ingestion_lifecycle()
