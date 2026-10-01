from services.retrieval.strategies.graph_strategy import GraphStrategy


def test_graph_strategy_retrieves_chunks():
    strategy = GraphStrategy()

    results = strategy.retrieve(
        "How are access reviews performed?"
    )

    assert results
    assert len(results) == 47

    result = results[0]

    assert result.source == "graph"
    assert result.document_id is not None
    assert result.document_version_id is not None
    assert result.chunk_id is not None
    assert result.text
