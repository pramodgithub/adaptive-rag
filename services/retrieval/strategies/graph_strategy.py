import re

from core.schemas.retrieval import RetrievalResult
from services.graph.neo4j_service import Neo4jService
from services.retrieval.strategies.base import RetrievalStrategy


class GraphStrategy(RetrievalStrategy):

    def __init__(self):
        self.graph_db = Neo4jService()

    def retrieve(self, query: str) -> list[RetrievalResult]:
        control_ids = re.findall(r"\bCC\d+\.\d+(?:\.\d+)?\b", query.upper())

        if control_ids:
            return self._retrieve_by_control(control_ids)

        return self._retrieve_related_chunks(query)

    def _retrieve_by_control(self, control_ids: list[str]) -> list[RetrievalResult]:
        cypher = """
        MATCH (d:Document)-[:HAS_VERSION]->(v:DocumentVersion)-[:HAS_CHUNK]->(c:Chunk)
        WHERE c.identifier IN $control_ids
        RETURN
            d.id AS document_id,
            d.title AS document_title,
            v.id AS document_version_id,
            c.id AS chunk_id,
            c.chunk_index AS chunk_index,
            c.page_start AS page_number,
            c.text AS text
        ORDER BY c.chunk_index
        """

        rows = self.graph_db.run(
            cypher,
            {"control_ids": control_ids},
        )

        return self._to_results(rows)

    def _retrieve_related_chunks(self, query: str) -> list[RetrievalResult]:
        keywords = [
            word.lower()
            for word in re.findall(r"\b[a-zA-Z]{4,}\b", query)
        ]

        cypher = """
        MATCH (d:Document)-[:HAS_VERSION]->(v:DocumentVersion)-[:HAS_CHUNK]->(c:Chunk)
        WHERE any(keyword IN $keywords
                WHERE toLower(c.text) CONTAINS keyword)
        RETURN
            d.id AS document_id,
            d.title AS document_title,
            v.id AS document_version_id,
            c.id AS chunk_id,
            c.chunk_index AS chunk_index,
            c.page_start AS page_number,
            c.text AS text
        ORDER BY c.chunk_index
        LIMIT 10
        """

        rows = self.graph_db.run(
            cypher,
            {"keywords": keywords},
        )

        return self._to_results(rows)

    @staticmethod
    def _to_results(rows: list[dict]) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_version_id=row["document_version_id"],
                chunk_index=row["chunk_index"],
                page_number=row["page_number"],
                document_title=row["document_title"],
                text=row["text"],
                score=1.0,
                source="graph",
            )
            for row in rows
        ]
