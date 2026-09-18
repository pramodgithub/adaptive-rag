import sys

from database.models.chunk import Chunk
from database.models.document_version import DocumentVersion
from database.session import SessionLocal


def fail(message: str):
    print(f"FAIL: {message}")
    sys.exit(1)


def find_gdpr_version(db):
    versions = (
        db.query(DocumentVersion)
        .join(DocumentVersion.document)
        .filter(
            DocumentVersion.file_name.ilike("%gdpr%"),
        )
        .order_by(DocumentVersion.version.desc())
        .all()
    )

    if not versions:
        fail("No GDPR document version found in database.")

    return versions[0]


def assert_true(condition: bool, message: str):
    if not condition:
        fail(message)

    print(f"PASS: {message}")


def main():
    db = SessionLocal()

    try:
        document_version = find_gdpr_version(db)

        print(
            f"\nGDPR document version: {document_version.id}"
        )

        print(
            f"Processing status: "
            f"{document_version.processing_status}"
        )

        assert_true(
            document_version.parsed_text_path is not None,
            "GDPR has parsed artifact",
        )

        assert_true(
            document_version.chunk_count is not None,
            "GDPR has chunk count",
        )

        chunks = (
            db.query(Chunk)
            .filter(
                Chunk.document_version_id == document_version.id
            )
            .order_by(Chunk.chunk_index)
            .all()
        )

        assert_true(
            len(chunks) > 0,
            "GDPR chunks exist in database",
        )

        assert_true(
            len(chunks) == document_version.chunk_count,
            (
                f"DB chunk count matches document_version.chunk_count "
                f"({len(chunks)})"
            ),
        )

        # ---------------------------------------------------------
        # Basic chunk invariants
        # ---------------------------------------------------------

        for expected_index, chunk in enumerate(chunks):
            assert_true(
                chunk.chunk_index == expected_index,
                f"Chunk index {expected_index} is sequential",
            )

            assert_true(
                bool(chunk.text.strip()),
                f"Chunk {chunk.chunk_index} contains text",
            )

            assert_true(
                len(chunk.text) <= 3200,
                f"Chunk {chunk.chunk_index} <= 3200 characters",
            )

        # ---------------------------------------------------------
        # GDPR semantic validation
        # ---------------------------------------------------------

        all_text = "\n".join(chunk.text for chunk in chunks)

        assert_true(
            "Article 32" in all_text,
            "GDPR Article 32 exists in persisted chunks",
        )

        assert_true(
            "Security of processing" in all_text,
            "GDPR Article 32 title is present",
        )

        # Find the chunk containing Article 32.
        article_32_chunks = [
            chunk
            for chunk in chunks
            if "Article 32" in chunk.text
        ]

        assert_true(
            len(article_32_chunks) > 0,
            "Article 32 has a persisted chunk",
        )

        article_32 = article_32_chunks[0]

        print(
            "\nArticle 32 chunk:"
        )
        print(
            f"  chunk_index={article_32.chunk_index}"
        )
        print(
            f"  page_number={article_32.page_number}"
        )
        print(
            f"  text_length={len(article_32.text)}"
        )

        print(
            "\nFirst 500 characters:"
        )
        print(article_32.text[:500])

        # ---------------------------------------------------------
        # Verify GDPR articles are represented
        # ---------------------------------------------------------

        article_numbers = set()

        for chunk in chunks:
            for number in range(1, 100):
                marker = f"Article {number}"

                if marker in chunk.text:
                    article_numbers.add(number)

        assert_true(
            len(article_numbers) >= 20,
            (
                f"GDPR article coverage detected "
                f"({len(article_numbers)} articles)"
            ),
        )

        # ---------------------------------------------------------
        # Verify page information survived persistence
        # ---------------------------------------------------------

        chunks_with_pages = [
            chunk
            for chunk in chunks
            if chunk.page_number is not None
        ]

        assert_true(
            len(chunks_with_pages) > 0,
            "Persisted GDPR chunks contain page numbers",
        )

        # ---------------------------------------------------------
        # Summary
        # ---------------------------------------------------------

        print("\n" + "=" * 60)
        print("GDPR CHUNKING INTEGRATION TEST PASSED")
        print("=" * 60)

        print(f"Document version : {document_version.id}")
        print(f"Chunks           : {len(chunks)}")
        print(f"Articles detected: {len(article_numbers)}")
        print(
            f"Chunks with page : "
            f"{len(chunks_with_pages)}/{len(chunks)}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
