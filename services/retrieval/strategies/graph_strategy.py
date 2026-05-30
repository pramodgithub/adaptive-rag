from core.schemas.retrieval import RetrievalResult
from services.graph.neo4j_service import Neo4jService
from services.retrieval.strategies.base import RetrievalStrategy


class GraphStrategy(RetrievalStrategy):

    def __init__(self):

        self.graph_db = Neo4jService()

    def retrieve(self, query: str):

        cypher = """
        MATCH (p:Pod)-[:RUNS_ON]->(n:Node)
        RETURN p.name as pod,n.name as node
        """

        rows = self.graph_db.run(
            cypher
        )

        return [

            RetrievalResult(
                text=f"{r['pod']} runs on {r['node']}",
                score=0.9,
                source="graph"
            )

            for r in rows
        ]
