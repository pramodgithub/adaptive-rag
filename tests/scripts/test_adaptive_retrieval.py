import uuid

from graph.workflow import graph


QUERIES = [
    {
        "name": "explicit_control",
        "query": "CC6.1.4",
        "expected_strategies": ["vector", "graph"],
    },
    {
        "name": "relationship_query",
        "query": "What requirements are related to CC6.1.4?",
        "expected_strategies": ["vector", "graph"],
    },
    {
        "name": "semantic_vector",
        "query": "data protection impact assessment",
        "expected_strategies": ["vector"],
    },
]


def print_results(results):
    print(f"Results: {len(results)}")

    for index, result in enumerate(results):
        print(
            f"  [{index}] "
            f"source={result.source} "
            f"score={result.score:.4f} "
            f"chunk={result.chunk_index} "
            f"page={result.page_number}"
        )


def assert_result_contract(results):
    assert isinstance(results, list)

    for result in results:
        assert result.chunk_id is not None
        assert result.document_id is not None
        assert result.document_version_id is not None
        assert result.text
        assert result.source in {"vector", "graph"}
        assert 0.0 <= result.score <= 1.0


def assert_no_duplicate_chunks(results):
    chunk_ids = [result.chunk_id for result in results]

    assert len(chunk_ids) == len(set(chunk_ids)), (
        "Duplicate chunks found in final retrieval results"
    )


def run_query(test_case):
    query = test_case["query"]

    print("\n" + "=" * 70)
    print(f"QUERY: {query}")
    print("=" * 70)

    execution_id = str(uuid.uuid4())

    result = graph.invoke(
        {
            "query": query,
            "retry_count": 0,
            "execution_id": execution_id,
            "node_metrics": {},
        }
    )

    strategies = result.get("strategies", [])
    all_results = result.get("all_results", [])
    retrieved = result.get("retrieved", [])

    print(f"Execution ID: {execution_id}")
    print(f"Strategies: {strategies}")
    print(f"All results: {len(all_results)}")
    print(f"Final results: {len(retrieved)}")

    print("\nFinal results:")
    print_results(retrieved)

    print("\nRetrieval evaluation:")
    evaluation = result.get("retrieval_evaluation")

    if evaluation:
        print(f"  relevance={evaluation.relevance}")
        print(f"  coverage={evaluation.coverage}")
        print(f"  authority={evaluation.authority}")
        print(f"  completeness={evaluation.completeness}")
        print(f"  consistency={evaluation.consistency}")
        print(f"  confidence={evaluation.confidence}")
        print(f"  sufficient={evaluation.sufficient}")
        print(f"  reason={evaluation.reason}")

    # ---------------------------------------------------------
    # Guardrail 1: Planner contract
    # ---------------------------------------------------------

    expected = set(test_case["expected_strategies"])
    actual = set(strategies)

    assert actual == expected, (
        f"Unexpected strategies. "
        f"Expected={expected}, Actual={actual}"
    )

    # ---------------------------------------------------------
    # Guardrail 2: Retrieval contract
    # ---------------------------------------------------------

    assert_result_contract(all_results)
    assert_result_contract(retrieved)

    # ---------------------------------------------------------
    # Guardrail 3: Final top-k
    # ---------------------------------------------------------

    assert len(retrieved) <= 5, (
        f"Final retrieval returned {len(retrieved)} results"
    )

    # ---------------------------------------------------------
    # Guardrail 4: No duplicate evidence
    # ---------------------------------------------------------

    assert_no_duplicate_chunks(retrieved)

    # ---------------------------------------------------------
    # Guardrail 5: Strategy provenance
    # ---------------------------------------------------------

    sources = {result.source for result in retrieved}

    assert sources.issubset({"vector", "graph"})

    if "graph" in expected:
        print(f"\nSources returned: {sources}")

    print("\nPASS")

    return result


def test_explicit_control():
    run_query(QUERIES[0])


def test_relationship_query():
    run_query(QUERIES[1])


def test_semantic_vector():
    run_query(QUERIES[2])


if __name__ == "__main__":
    for test_case in QUERIES:
        run_query(test_case)
