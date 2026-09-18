import os

from services.ingestion.normalization.document_normalizer import (
    DocumentNormalizer,
)
from services.ingestion.parsers.docling_parser import DoclingParser


FILE_PATH = os.getenv(
    "TEST_DOCUMENT",
    "tests/data/soc2.pdf",
)


def main():
    parser = DoclingParser()
    normalizer = DocumentNormalizer()

    print(f"Parsing: {FILE_PATH}")

    document = parser.parse(FILE_PATH)

    print(
        f"Before normalization: "
        f"{len(document.elements)} elements"
    )

    normalized = normalizer.normalize(document)

    print(
        f"After normalization: "
        f"{len(normalized.elements)} elements"
    )

    removed = (
        len(document.elements)
        - len(normalized.elements)
    )

    print(f"Removed elements: {removed}")

    print("\n--- Validation ---")

    assert normalized.title
    assert normalized.page_count > 0
    assert normalized.elements

    for index, element in enumerate(
        normalized.elements,
        start=1,
    ):
        assert element.element_type is not None

        if element.element_type.value != "image":
            assert element.text.strip(), (
                f"Element {index} has empty text"
            )

        if element.page_start is not None:
            assert 1 <= element.page_start <= normalized.page_count

        if element.page_end is not None:
            assert 1 <= element.page_end <= normalized.page_count

        assert isinstance(element.metadata, dict)

    print("PASS: Canonical document invariants")
    print("PASS: Normalization completed successfully")


if __name__ == "__main__":
    main()
