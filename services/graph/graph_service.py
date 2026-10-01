from neo4j import GraphDatabase

from core.config.settings import settings


class GraphService:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(
                settings.NEO4J_USERNAME,
                settings.NEO4J_PASSWORD,
            ),
        )

    def close(self):
        self.driver.close()

    def create_document_graph(self, document, document_version, chunks):
        with self.driver.session() as session:
            session.execute_write(
                self._create_graph,
                document,
                document_version,
                chunks,
            )

    @staticmethod
    def _create_graph(tx, document, document_version, chunks):
        tx.run(
            """
            MERGE (d:Document {id: $document_id})
            SET d.title = $title,
                d.source = $source,
                d.document_type = $document_type

            MERGE (v:DocumentVersion {id: $version_id})
            SET v.version = $version

            MERGE (d)-[:HAS_VERSION]->(v)
            """,
            document_id=str(document.id),
            title=document.title,
            source=document.source,
            document_type=document.document_type,
            version_id=str(document_version.id),
            version=document_version.version,
        )

        for chunk in chunks:
            tx.run(
                """
                MERGE (c:Chunk {id: $chunk_id})
                SET c.chunk_index = $chunk_index,
                    c.text = $text,
                    c.page_start = $page_start,
                    c.page_end = $page_end,
                    c.section_path = $section_path,
                    c.structure_type = $structure_type,
                    c.identifier = $identifier

                WITH c
                MATCH (v:DocumentVersion {id: $version_id})
                MERGE (v)-[:HAS_CHUNK]->(c)
                """,
                chunk_id=str(chunk.id),
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_path=chunk.section_path,
                structure_type=chunk.structure_type,
                identifier=chunk.identifier,
                version_id=str(document_version.id),
            )
