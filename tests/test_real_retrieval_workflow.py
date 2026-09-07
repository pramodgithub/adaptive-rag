from graph.workflow import graph


def test_real_retrieval_workflow():
    state = {
        "execution_id": "real-retrieval-test",
        "query": "How frequently are access reviews performed?",
        "strategies": [],
        "rewritten_query": "",
        "retrieved": [],
        "all_results": [],
        "retrieval_evaluation": None,
        "retrieval_judgment": None,
        "answer": "",
        "answer_evaluation": None,
        "metadata": {},
        "retry_count": 0,
        "node_metrics": {},
        "assessment_context": None,
    }

    result = graph.invoke(state)

    print("\n" + "=" * 60)
    print("REAL RETRIEVAL WORKFLOW RESULT")
    print("=" * 60)

    print("\nAnswer:")
    print(result.get("answer"))

    print("\nRetrieval Evaluation:")
    print(result.get("retrieval_evaluation"))

    print("\nRetrieval Judgment:")
    print(result.get("retrieval_judgment"))

    print("\nAnswer Evaluation:")
    print(result.get("answer_evaluation"))

    print("\nRetry Count:")
    print(result.get("retry_count"))

    print("\nMetadata:")
    print(result.get("metadata"))

    print("\nNode Metrics:")
    print(result.get("node_metrics"))

    print("\nRetrieved Sources:")
    for index, item in enumerate(result.get("retrieved", []), start=1):
        print(
            f"\n[{index}] score={item.score:.4f}"
            f" | title={getattr(item, 'document_title', None)}"
        )
        print(item.text[:500])

    assert result.get("answer"), "Workflow did not generate an answer."
    assert result.get("retrieved"), "Workflow returned no retrieved evidence."

    print("\n[PASS] Real retrieval workflow completed successfully.")


if __name__ == "__main__":
    test_real_retrieval_workflow()
