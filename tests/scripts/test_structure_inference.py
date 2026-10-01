import os

from services.ingestion.domain.elements import DocumentElement, ElementType
from services.ingestion.normalization.document_normalizer import (
    DocumentNormalizer,
)
from services.ingestion.parsers.docling_parser import DoclingParser
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
)
from services.ingestion.structure.soc2_strategy import SOC2StructureStrategy


FILE_PATH = os.getenv(
    "TEST_DOCUMENT",
    "tests/data/soc2.pdf",
)


def make_element(text: str) -> DocumentElement:
    return DocumentElement(
        element_type=ElementType.PARAGRAPH,
        text=text,
        page_start=1,
        page_end=1,
        section_path=[],
        metadata={},
        table=None,
    )


def test_soc2_strategy_directly():
    print("\n" + "=" * 70)
    print("TEST 1: SOC2 STRATEGY DIRECT TEST")
    print("=" * 70)

    strategy = SOC2StructureStrategy()

    valid_cases = [
        ("CC6.1", "CC6.1"),
        ("CC6.1.4", "CC6.1.4"),
        ("CC6.8", "CC6.8"),
        ("CC4.1.8", "CC4.1.8"),
        ("A1.1", "A1.1"),
        ("CC6.8: The entity implements controls.", "CC6.8"),
        ("CC6.1.4: Logical access controls.", "CC6.1.4"),
    ]

    for text, expected_identifier in valid_cases:
        result = strategy.infer(
            element=make_element(text),
            previous_elements=[],
            current_path=[],
        )

        assert result is not None, (
            f"SOC2 strategy did not match: {text}"
        )

        assert result.identifier == expected_identifier, (
            f"Expected {expected_identifier}, "
            f"got {result.identifier}"
        )

        assert result.structure_type == "control"
        assert result.source == "soc2.control"
        assert result.confidence == 0.98

        print(
            f"PASS | {text[:50]:50} | "
            f"identifier={result.identifier}"
        )

    invalid_cases = [
        "The entity implements controls.",
        "Access management policy",
        "AC-2: Account Management",
        "Article 6: Lawfulness of processing",
        "",
    ]

    for text in invalid_cases:
        result = strategy.infer(
            element=make_element(text),
            previous_elements=[],
            current_path=[],
        )

        assert result is None, (
            f"SOC2 strategy incorrectly matched: {text}"
        )

        print(
            f"PASS | Correctly rejected: "
            f"{text[:50]}"
        )

    print("\nPASS: Direct SOC2 strategy tests")


def test_actual_document():
    print("\n" + "=" * 70)
    print("TEST 2: ACTUAL SOC2 DOCUMENT")
    print("=" * 70)

    parser = DoclingParser()
    normalizer = DocumentNormalizer()
    structure = StructureInferenceService()

    print(f"Parsing: {FILE_PATH}")

    document = parser.parse(FILE_PATH)
    normalized = normalizer.normalize(document)
    inferred = structure.infer(normalized)

    assert len(inferred.elements) == len(normalized.elements)
    assert inferred.page_count == normalized.page_count
    assert inferred.title == normalized.title

    print(f"Parsed elements: {len(normalized.elements)}")
    print(f"Inferred elements: {len(inferred.elements)}")
    print(f"Page count: {inferred.page_count}")
    print(f"Title: {inferred.title}")

    soc2_controls = []
    generic_structures = []
    no_structures = []
    all_identifiers = []

    for index, element in enumerate(
        inferred.elements,
        start=1,
    ):
        assert isinstance(element.section_path, list)
        assert "structure" in element.metadata

        structure_metadata = element.metadata["structure"]

        assert isinstance(structure_metadata, dict)

        assert "section_path" in structure_metadata
        assert "confidence" in structure_metadata
        assert "source" in structure_metadata
        assert "structure_type" in structure_metadata
        assert "identifier" in structure_metadata
        assert "parent_identifier" in structure_metadata

        assert (
            structure_metadata["section_path"]
            == element.section_path
        )

        source = structure_metadata["source"]
        identifier = structure_metadata["identifier"]
        structure_type = structure_metadata["structure_type"]

        if source == "soc2.control":
            soc2_controls.append(
                {
                    "index": index,
                    "page": element.page_start,
                    "text": element.text,
                    "identifier": identifier,
                    "structure_type": structure_type,
                    "section_path": element.section_path,
                }
            )

        elif source == "generic":
            generic_structures.append(
                {
                    "index": index,
                    "page": element.page_start,
                    "text": element.text,
                    "identifier": identifier,
                    "structure_type": structure_type,
                }
            )

        elif source == "none":
            no_structures.append(
                {
                    "index": index,
                    "page": element.page_start,
                    "text": element.text,
                }
            )

        if identifier:
            all_identifiers.append(
                {
                    "index": index,
                    "page": element.page_start,
                    "identifier": identifier,
                    "source": source,
                    "text": element.text,
                }
            )

        if element.element_type == ElementType.HEADING:
            assert element.section_path, (
                f"Heading has empty section path: "
                f"element {index}"
            )

            assert (
                element.section_path[-1]
                == element.text
            ), (
                f"Heading section path mismatch: "
                f"element {index}"
            )

    print("\n--- Structure Summary ---")

    print(
        f"SOC2 controls detected : "
        f"{len(soc2_controls)}"
    )

    print(
        f"Generic structures     : "
        f"{len(generic_structures)}"
    )

    print(
        f"No structure           : "
        f"{len(no_structures)}"
    )

    print(
        f"Identifiers detected   : "
        f"{len(all_identifiers)}"
    )

    print("\n--- Detected SOC2 Controls ---")

    if soc2_controls:
        for item in soc2_controls[:30]:
            print(
                f"[{item['index']}] "
                f"Page {item['page']} | "
                f"{item['identifier']} | "
                f"{item['structure_type']} | "
                f"{item['text'][:120]}"
            )
    else:
        print("WARNING: No SOC2 controls detected")

    print("\n--- All Detected Identifiers ---")

    for item in all_identifiers[:50]:
        print(
            f"[{item['index']}] "
            f"Page {item['page']} | "
            f"{item['identifier']} | "
            f"{item['source']} | "
            f"{item['text'][:100]}"
        )

    print("\n--- First 30 Elements ---")

    for index, element in enumerate(
        inferred.elements[:30],
        start=1,
    ):
        metadata = element.metadata["structure"]

        print(
            f"\n[{index}] "
            f"{element.element_type.value} | "
            f"Page {element.page_start}"
        )

        print(
            f"Text: "
            f"{element.text[:150]}"
        )

        print(
            f"Section: "
            f"{element.section_path}"
        )

        print(
            f"Source: "
            f"{metadata['source']}"
        )

        print(
            f"Type: "
            f"{metadata['structure_type']}"
        )

        print(
            f"Identifier: "
            f"{metadata['identifier']}"
        )

        print(
            f"Parent: "
            f"{metadata['parent_identifier']}"
        )

        print(
            f"Confidence: "
            f"{metadata['confidence']}"
        )

    print("\n" + "=" * 70)
    print("ALL ELEMENTS CONTAINING POSSIBLE SOC2 IDENTIFIERS")
    print("=" * 70)

    for index, element in enumerate(
        inferred.elements,
        start=1,
    ):
        text = element.text.strip()

        if any(
            token in text.upper()
            for token in ["CC6", "CC4", "CC5", "CC7", "CC8", "CC9"]
        ):
            metadata = element.metadata["structure"]

            print(
                f"\n[{index}] Page {element.page_start}"
            )

            print(f"Text: {text[:300]}")

            print(
                f"Source: "
                f"{metadata['source']}"
            )

            print(
                f"Type: "
                f"{metadata['structure_type']}"
            )

            print(
                f"Identifier: "
                f"{metadata['identifier']}"
            )

            print(
                f"Parent: "
                f"{metadata['parent_identifier']}"
            )

            print(
                f"Section: "
                f"{element.section_path}"
            )

    assert len(inferred.elements) == len(
        normalized.elements
    )

    assert inferred.page_count == normalized.page_count

    assert inferred.title == normalized.title

    assert all(
        isinstance(element.section_path, list)
        for element in inferred.elements
    )

    assert all(
        "structure" in element.metadata
        for element in inferred.elements
    )

    assert soc2_controls, (
        "No SOC2 controls detected in actual document. "
        "Inspect the parser output and regex."
    )

    print("\nPASS: Element count preserved")
    print("PASS: Document metadata preserved")
    print("PASS: Structure metadata present")
    print("PASS: Heading inference")
    print("PASS: SOC2 controls detected")
    print("PASS: Structure inference completed")

    print("\n" + "=" * 70)
    print("SOC2 IDENTIFIER SUMMARY")
    print("=" * 70)

    for item in all_identifiers:
        print(
            f"{item['identifier']:15} "
            f"| {item['source']:20} "
            f"| Page {item['page']} "
            f"| {item['text'][:100]}"
        )


def main():
    test_soc2_strategy_directly()
    test_actual_document()

    print("\n" + "=" * 70)
    print("ALL STRUCTURE INFERENCE TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
