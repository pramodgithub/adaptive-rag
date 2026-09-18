import sys

from services.ingestion.parsers.factory import ParserFactory


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

    document = parser.parse(GDPR_PATH)

    print("\nGDPR parser result")
    print("=" * 60)
    print("Title:", document.title)
    print("Pages:", document.page_count)
    print("Elements:", len(document.elements))

    assert_true(
        document.page_count > 0,
        "Document has pages",
    )

    assert_true(
        len(document.elements) > 0,
        "Document has canonical elements",
    )

    assert_true(
        document.title,
        "Document has a title",
    )

    # Basic element validation
    non_empty = [
        element
        for element in document.elements
        if element.text.strip()
    ]

    assert_true(
        len(non_empty) > 0,
        "Document contains non-empty elements",
    )

    # Page metadata
    elements_with_pages = [
        element
        for element in document.elements
        if element.page_start is not None
    ]

    assert_true(
        len(elements_with_pages) > 0,
        "Elements contain page metadata",
    )

    # GDPR-specific content checks
    all_text = "\n".join(
        element.text
        for element in document.elements
    )

    assert_true(
        "Article 32" in all_text,
        "GDPR Article 32 exists in parsed content",
    )

    assert_true(
        "Security of processing" in all_text,
        "GDPR Article 32 title exists",
    )

    assert_true(
        "Article 1" in all_text,
        "GDPR Article 1 exists",
    )

    # Check element types
    element_types = {
        element.element_type.value
        for element in document.elements
    }

    print(
        "\nElement types:",
        sorted(element_types),
    )

    print("\n" + "=" * 60)
    print("GDPR PARSER TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
