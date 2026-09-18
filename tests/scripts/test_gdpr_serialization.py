import sys

from services.ingestion.parsers.factory import ParserFactory
from services.ingestion.domain.serialization import (
    document_to_dict,
    document_from_dict,
)


GDPR_PATH = "/app/tests/data/CELEX_32016R0679_EN_TXT.pdf"


def fail(message: str):
    print(f"FAIL: {message}")
    sys.exit(1)


def assert_true(condition: bool, message: str):
    if not condition:
        fail(message)

    print(f"PASS: {message}")


def main():
    parser = ParserFactory.get_parser(
        "application/pdf"
    )

    original = parser.parse(GDPR_PATH)

    print("\nOriginal document")
    print("=" * 60)
    print("Title:", original.title)
    print("Pages:", original.page_count)
    print("Elements:", len(original.elements))

    # Serialize
    data = document_to_dict(original)

    assert_true(
        isinstance(data, dict),
        "Document serializes to dictionary",
    )

    assert_true(
        "elements" in data,
        "Serialized document contains elements",
    )

    assert_true(
        len(data["elements"]) == len(original.elements),
        "Serialized element count matches original",
    )

    # Deserialize
    restored = document_from_dict(data)

    print("\nRestored document")
    print("=" * 60)
    print("Title:", restored.title)
    print("Pages:", restored.page_count)
    print("Elements:", len(restored.elements))

    assert_true(
        restored.title == original.title,
        "Title survives serialization",
    )

    assert_true(
        restored.page_count == original.page_count,
        "Page count survives serialization",
    )

    assert_true(
        len(restored.elements) == len(original.elements),
        "Element count survives serialization",
    )

    # ---------------------------------------------------------
    # Validate representative elements
    # ---------------------------------------------------------

    for index in [0, len(original.elements) // 2, -1]:
        original_element = original.elements[index]
        restored_element = restored.elements[index]

        assert_true(
            restored_element.element_type
            == original_element.element_type,
            f"Element {index} type survives",
        )

        assert_true(
            restored_element.text
            == original_element.text,
            f"Element {index} text survives",
        )

        assert_true(
            restored_element.page_start
            == original_element.page_start,
            f"Element {index} page_start survives",
        )

        assert_true(
            restored_element.page_end
            == original_element.page_end,
            f"Element {index} page_end survives",
        )

        assert_true(
            restored_element.section_path
            == original_element.section_path,
            f"Element {index} section_path survives",
        )

        assert_true(
            restored_element.metadata
            == original_element.metadata,
            f"Element {index} metadata survives",
        )

    # ---------------------------------------------------------
    # GDPR-specific content validation
    # ---------------------------------------------------------

    original_text = "\n".join(
        element.text
        for element in original.elements
    )

    restored_text = "\n".join(
        element.text
        for element in restored.elements
    )

    assert_true(
        "Article 1" in restored_text,
        "Article 1 survives serialization",
    )

    assert_true(
        "Article 32" in restored_text,
        "Article 32 survives serialization",
    )

    assert_true(
        "Security of processing" in restored_text,
        "Article 32 title survives serialization",
    )

    assert_true(
        restored_text == original_text,
        "Complete document text survives serialization",
    )

    print("\n" + "=" * 60)
    print("GDPR SERIALIZATION TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
