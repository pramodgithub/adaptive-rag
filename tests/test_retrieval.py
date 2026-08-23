from services.retrieval.retrieval_service import RetrievalService


def main():
    query = "What is the organization's employee security awareness training?"

    service = RetrievalService()

    results = service.search(query, top_k=3)

    print(f"\nQuery: {query}")
    print(f"Results: {len(results)}")

    for index, result in enumerate(results, start=1):
        print(f"\n--- Result {index} ---")
        print(f"Score: {result.score:.4f}")
        print(f"Source: {result.source}")
        print(f"Document ID: {result.document_id}")
        print(f"Document Version ID: {result.document_version_id}")
        print(f"Chunk ID: {result.chunk_id}")
        print(f"Chunk Index: {result.chunk_index}")
        print(f"Page Number: {result.page_number}")
        print(f"Document Title: {result.document_title}")
        print(result.text[:1000])


if __name__ == "__main__":
    main()
