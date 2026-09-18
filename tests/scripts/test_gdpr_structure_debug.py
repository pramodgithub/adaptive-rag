import sys
from collections import Counter

from services.ingestion.parsers.factory import ParserFactory
from services.ingestion.structure.structure_inference import StructureInferenceService


GDPR_PATH = "/app/tests/data/CELEX_32016R0679_EN_TXT.pdf"


def fail(message: str):
    print(f"FAIL: {message}")
    sys.exit(1)


def assert_true(condition: bool, message: str):
    if not condition:
        fail(message)
    print(f"PASS: {message}")


def main():
    parser = ParserFactory.get_parser("application/pdf")
    document = parser.parse(GDPR_PATH)

    structured = StructureInferenceService().infer(document)

    print("\nGDPR structure inference")
    print("=" * 60)
    print("Elements:", len(structured.elements))

    assert_true(
        len(structured.elements) == len(document.elements),
        "Structure inference preserves element count",
    )

    structure_types = Counter()
    articles = {}
    article_titles = {}

    for index, element in enumerate(structured.elements):
        structure = element.metadata.get("structure", {})
        structure_type = structure.get("structure_type")

        if structure_type:
            structure_types[structure_type] += 1

        if structure_type == "article":
            articles[structure.get("identifier")] = (index, element)

        if structure_type == "article_title":
            article_titles[structure.get("identifier")] = (index, element)

    print("\nStructure types:")
    for structure_type, count in sorted(structure_types.items()):
        print(f"  {structure_type}: {count}")

    print("\nArticles detected:", len(articles))
    print("Article titles detected:", len(article_titles))

    assert_true(
        len(articles) > 0,
        "GDPR articles were detected",
    )

    assert_true(
        "1" in articles,
        "Article 1 was detected",
    )

    assert_true(
        "32" in articles,
        "Article 32 was detected",
    )

    assert_true(
        "32" in article_titles,
        "Article 32 title was detected",
    )

    article_32_index, article_32 = articles["32"]
    title_index, article_32_title = article_titles["32"]

    article_32_structure = article_32.metadata["structure"]
    title_structure = article_32_title.metadata["structure"]

    assert_true(
        article_32_structure["source"] == "gdpr.article",
        "Article 32 uses GDPR article strategy",
    )

    assert_true(
        article_32_structure["confidence"] >= 0.98,
        "Article 32 has expected inference confidence",
    )

    assert_true(
        article_32_structure["identifier"] == "32",
        "Article 32 identifier is correct",
    )

    assert_true(
        article_32_structure["structure_type"] == "article",
        "Article 32 structure type is correct",
    )

    assert_true(
        title_index == article_32_index + 1,
        "Article 32 title immediately follows Article 32",
    )

    assert_true(
        article_32_title.text == "Security of processing",
        "Article 32 title text is correct",
    )

    assert_true(
        title_structure["source"] == "gdpr.article_title",
        "Article 32 title uses GDPR article-title strategy",
    )

    assert_true(
        title_structure["structure_type"] == "article_title",
        "Article 32 title structure type is correct",
    )

    assert_true(
        title_structure["identifier"] == "32",
        "Article 32 title identifier is correct",
    )

    assert_true(
        title_structure["parent_identifier"] == "32",
        "Article 32 title references parent Article 32",
    )

    assert_true(
        article_32_title.section_path == article_32.section_path,
        "Article 32 title preserves article section path",
    )

    content_after_title = []

    for element in structured.elements[title_index + 1:]:
        structure = element.metadata.get("structure", {})

        if (
            structure.get("structure_type") == "article"
            and structure.get("identifier") != "32"
        ):
            break

        content_after_title.append(element)

    assert_true(
        len(content_after_title) > 0,
        "Article 32 contains content after its title",
    )

    content_with_article_path = [
        element
        for element in content_after_title
        if element.section_path == article_32.section_path
    ]

    assert_true(
        len(content_with_article_path) > 0,
        "Article 32 content inherits article section",
    )

    numeric_article_ids = []

    for identifier in articles:
        try:
            numeric_article_ids.append(int(identifier))
        except (TypeError, ValueError):
            fail(f"Invalid GDPR article identifier: {identifier}")

    assert_true(
        len(numeric_article_ids) == len(articles),
        "All detected article identifiers are numeric",
    )

    print("\nFirst 20 article identifiers:")
    for identifier in numeric_article_ids[:20]:
        print(f"  Article {identifier}")

    print("\nArticle 32 structure:")
    print("-" * 60)

    for index in range(
        max(0, article_32_index),
        min(article_32_index + 6, len(structured.elements)),
    ):
        element = structured.elements[index]
        structure = element.metadata.get("structure", {})

        print(
            f"type={element.element_type.value} "
            f"identifier={structure.get('identifier')} "
            f"structure_type={structure.get('structure_type')} "
            f"page={element.page_start} "
            f"section={element.section_path} "
            f"text={element.text[:100]!r}"
        )

    print("\n" + "=" * 60)
    print("GDPR STRUCTURE INFERENCE TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
