import sys
from collections import Counter

from services.ingestion.parsers.factory import ParserFactory
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
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

    document = parser.parse(GDPR_PATH)

    inference = StructureInferenceService()

    structured = inference.infer(document)

    print("\nGDPR structure inference")
    print("=" * 60)
    print("Elements:", len(structured.elements))

    assert_true(
        len(structured.elements) == len(document.elements),
        "Structure inference preserves element count",
    )

    # ---------------------------------------------------------
    # Inspect inferred structure
    # ---------------------------------------------------------

    structure_types = Counter()
    article_ids = []
    recital_ids = []

    for element in structured.elements:
        structure = element.metadata.get(
            "structure",
            {},
        )

        structure_type = structure.get(
            "structure_type"
        )

        if structure_type:
            structure_types[structure_type] += 1

        if structure_type == "article":
            article_ids.append(
                structure.get("identifier")
            )

        if structure_type == "recital":
            recital_ids.append(
                structure.get("identifier")
            )

    print("\nStructure types:")
    for structure_type, count in sorted(
        structure_types.items()
    ):
        print(
            f"  {structure_type}: {count}"
        )

    print("\nArticles detected:", len(article_ids))
    print("Recitals detected:", len(recital_ids))

    # ---------------------------------------------------------
    # Basic article validation
    # ---------------------------------------------------------

    assert_true(
        len(article_ids) > 0,
        "GDPR articles were detected",
    )

    assert_true(
        "1" in article_ids,
        "Article 1 was detected",
    )

    assert_true(
        "32" in article_ids,
        "Article 32 was detected",
    )

    # ---------------------------------------------------------
    # Article structure metadata
    # ---------------------------------------------------------

    article_32_elements = [
        element
        for element in structured.elements
        if element.metadata.get("structure", {}).get(
            "structure_type"
        ) == "article"
        and element.metadata.get("structure", {}).get(
            "identifier"
        ) == "32"
    ]

    assert_true(
        len(article_32_elements) > 0,
        "Article 32 structure metadata exists",
    )

    article_32 = article_32_elements[0]

    structure = article_32.metadata["structure"]

    assert_true(
        structure["source"] == "gdpr.article",
        "Article 32 uses GDPR structure strategy",
    )

    assert_true(
        structure["confidence"] >= 0.98,
        "Article 32 has expected inference confidence",
    )

    assert_true(
        structure["identifier"] == "32",
        "Article 32 identifier is correct",
    )

    assert_true(
        structure["structure_type"] == "article",
        "Article 32 structure type is correct",
    )

    # ---------------------------------------------------------
    # Verify inheritance
    # ---------------------------------------------------------

    article_32_index = structured.elements.index(article_32)

    article_32_title_elements = [
        element
        for element in structured.elements[article_32_index + 1:]
        if element.metadata.get("structure", {}).get("structure_type") == "article_title"
        and element.metadata.get("structure", {}).get("identifier") == "32"
    ]

    assert_true(
        len(article_32_title_elements) == 1,
        "Article 32 title was detected",
    )

    article_32_title = article_32_title_elements[0]

    assert_true(
        article_32_title.section_path == article_32.section_path,
        "Article 32 title preserves article section",
    )

    assert_true(
        article_32_title.metadata["structure"]["parent_identifier"] == "32",
        "Article 32 title references parent article",
    )

    title_index = structured.elements.index(article_32_title)

    inherited_elements = []

    for element in structured.elements[title_index + 1:]:
        structure = element.metadata.get("structure", {})

        if (
            structure.get("structure_type") == "article"
            and structure.get("identifier") != "32"
        ):
            break

        if element.section_path == article_32.section_path:
            inherited_elements.append(element)

    assert_true(
        len(inherited_elements) > 0,
        "Article 32 content inherits article section",
    )

    # ---------------------------------------------------------
    # Validate article sequence
    # ---------------------------------------------------------

    numeric_article_ids = []

    for identifier in article_ids:
        try:
            numeric_article_ids.append(
                int(identifier)
            )
        except (TypeError, ValueError):
            fail(
                f"Invalid GDPR article identifier: "
                f"{identifier}"
            )

    assert_true(
        len(numeric_article_ids)
        == len(article_ids),
        "All detected article identifiers are numeric",
    )

    print("\nFirst 20 article identifiers:")

    for identifier in numeric_article_ids[:20]:
        print(f"  Article {identifier}")

    # ---------------------------------------------------------
    # Show Article 32 context
    # ---------------------------------------------------------

    print("\nArticle 32 structure:")
    print("-" * 60)

    for element in structured.elements[
        max(0, article_32_index - 1):
        article_32_index + 5
    ]:
        structure = element.metadata.get(
            "structure",
            {}
        )

        print(
            f"type={element.element_type.value} "
            f"identifier={structure.get('identifier')} "
            f"structure_type={structure.get('structure_type')} "
            f"page={element.page_start} "
            f"text={element.text[:100]!r}"
        )

    print("\n" + "=" * 60)
    print("GDPR STRUCTURE INFERENCE TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
