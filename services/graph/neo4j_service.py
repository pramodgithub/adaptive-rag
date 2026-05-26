from neo4j import GraphDatabase

from core.config.settings import settings


class Neo4jService:

    def __init__(self):

        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(
                settings.NEO4J_USERNAME,
                settings.NEO4J_PASSWORD
            )
        )

    def run(
        self,
        query: str,
        params: dict = None
    ):

        with self.driver.session() as session:

            result = session.run(
                query,
                params or {}
            )

            return [r.data() for r in result]
