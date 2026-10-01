from services.retrieval.strategies.graph_strategy import GraphStrategy


def test_graph_strategy_retrieves_chunks():
    strategy = GraphStrategy()

    results = strategy.retrieve(
        "How are access reviews performed?"
    )

    assert results
    assert len(results) <= 10
    assert all(result.source == "graph" for result in results)

    print(f"[PASS] Text graph retrieval returned {len(results)} chunks")


def test_graph_strategy_retrieves_control():
    strategy = GraphStrategy()

    results = strategy.retrieve(
        "Explain control CC6.1.4"
    )

    assert results
    assert all(result.source == "graph" for result in results)

    print(f"[PASS] Control graph retrieval returned {len(results)} chunks")


if __name__ == "__main__":
    test_graph_strategy_retrieves_chunks()
    test_graph_strategy_retrieves_control()
    print("[PASS] All GraphStrategy integration tests passed.")
