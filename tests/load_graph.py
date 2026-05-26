from services.graph.neo4j_service import Neo4jService


db = Neo4jService()


queries = [

    """
CREATE (:Pod {name:'pod-1'})
""",

    """
CREATE (:Node {name:'node-1'})
""",

    """
MATCH (p:Pod),(n:Node)
CREATE (p)-[:RUNS_ON]->(n)
"""
]


for q in queries:

    db.run(q)

print("Graph loaded")
