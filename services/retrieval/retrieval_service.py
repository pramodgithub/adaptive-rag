import re

from sqlalchemy import text

from core.embeddings.embedding_service import EmbeddingService
from core.schemas.evidence import EvidenceMetadata
from core.schemas.retrieval import RetrievalResult
from database.session import SessionLocal
from enums.document_status import DocumentStatus
from enums.processing_status import ProcessingStatus


# IDs a user may ask about directly.
# Controls / requirements: CC6.1.5, A.5.1, PI1.2, 8.3.1
_CONTROL_ID = re.compile(r"(?<![\w.])((?:[A-Za-z]{1,4}\.?)?\d+(?:\.\d+)+[a-z]?)(?![\w.])")
# Labelled provisions: Article 32, Clause 7
_LABELLED_ID = re.compile(r"\b(article|clause)\s+(\d+[a-z]?)\b", re.IGNORECASE)

_SELECT = """
    SELECT
        c.id AS chunk_id,
        c.document_version_id,
        dv.document_id,
        c.text,
        c.chunk_index,
        c.page_number,
        d.title,
        1 - (c.embedding <=> CAST(:embedding AS vector)) AS score,
        dv.source_type,
        dv.issuer,
        dv.jurisdiction,
        dv.authority_level,
        dv.publication_date,
        dv.effective_date,
        dv.expiration_date,
        dv.verification_status
    FROM chunks c
    JOIN document_versions dv
        ON dv.id = c.document_version_id
    JOIN documents d
        ON d.id = dv.document_id
    WHERE c.embedding IS NOT NULL
    AND d.status = :document_status
    AND dv.is_active = TRUE
    AND dv.processing_status = :processing_status
"""


class RetrievalService:

    def __init__(self):
        self.embedding_service = EmbeddingService()

    @staticmethod
    def _identifiers_in(query: str) -> tuple[list[str], list[tuple[str, str]]]:
        """IDs named in the question: control IDs and labelled provisions."""
        controls = list(dict.fromkeys(
            match.upper() for match in _CONTROL_ID.findall(query)
        ))
        labelled = list(dict.fromkeys(
            (label.lower(), number) for label, number in _LABELLED_ID.findall(query)
        ))
        return controls, labelled

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:

        embedding = self.embedding_service.embed(query)[0]

        params = {
            "embedding": str(embedding),
            "document_status": DocumentStatus.ACTIVE.value,
            "processing_status": ProcessingStatus.READY.value,
            "top_k": top_k,
        }

        controls, labelled = self._identifiers_in(query)

        with SessionLocal() as db:

            # 1. Exact ID match first. Vector search treats "CC6.1.5" and
            #    "CC6.1" as almost the same text; the stored identifier doesn't.
            exact_rows = []

            if controls or labelled:
                conditions = []

                if controls:
                    conditions.append("UPPER(c.identifier) = ANY(:control_ids)")
                    params["control_ids"] = controls

                for index, (label, number) in enumerate(labelled):
                    conditions.append(
                        f"(c.structure_type = :label_{index} "
                        f"AND c.identifier = :number_{index})"
                    )
                    params[f"label_{index}"] = label
                    params[f"number_{index}"] = number

                exact_rows = db.execute(
                    text(
                        _SELECT
                        + " AND (" + " OR ".join(conditions) + ")"
                        + " ORDER BY score DESC LIMIT :top_k"
                    ),
                    params,
                ).fetchall()

            # 2. Vector search fills the rest, as before.
            vector_rows = db.execute(
                text(
                    _SELECT
                    + " ORDER BY c.embedding <=> CAST(:embedding AS vector)"
                    + " LIMIT :top_k"
                ),
                params,
            ).fetchall()

        results: list[RetrievalResult] = []
        seen = set()

        for rows, source in ((exact_rows, "identifier"), (vector_rows, "vector")):
            for row in rows:
                if row.chunk_id in seen or len(results) >= top_k:
                    continue

                seen.add(row.chunk_id)
                results.append(self._to_result(row, source))

        return results

    @staticmethod
    def _to_result(row, source: str) -> RetrievalResult:
        return RetrievalResult(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_version_id=row.document_version_id,
            chunk_index=row.chunk_index,
            page_number=row.page_number,
            document_title=row.title,
            text=row.text,
            score=float(row.score),
            source=source,
            evidence=EvidenceMetadata(
                source_type=row.source_type,
                issuer=row.issuer,
                jurisdiction=row.jurisdiction,
                authority_level=row.authority_level,
                publication_date=row.publication_date,
                effective_date=row.effective_date,
                expiration_date=row.expiration_date,
                verification_status=row.verification_status,
            ) if row.authority_level else None
        )