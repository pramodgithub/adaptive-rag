import os

from services.ingestion.normalization.document_normalizer import (
    DocumentNormalizer,
)
from services.ingestion.parsers.docling_parser import DoclingParser
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
)


FILE_PATH = os.getenv(
    "TEST_DOCUMENT",
    "tests/data/soc2.pdf",
)


def main():
    parser = DoclingParser()
    normalizer = DocumentNormalizer()
    structure = StructureInferenceService()

    print(f"Parsing: {FILE_PATH}")

    document = parser.parse(FILE_PATH)
    normalized = normalizer.normalize(document)
    inferred = structure.infer(normalized)

    print(f"Elements: {len(inferred.elements)}")

    assert len(inferred.elements) == len(normalized.elements)
    assert inferred.page_count == normalized.page_count
    assert inferred.title == normalized.title

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

        assert (
            structure_metadata["section_path"]
            == element.section_path
        )

        if element.element_type.value == "heading":
            assert element.section_path
            assert element.section_path[-1] == element.text

    print("\n--- Inferred Structure ---")

    for index, element in enumerate(
        inferred.elements[:30],
        start=1,
    ):
        print(
            f"[{index}] "
            f"{element.element_type.value} | "
            f"Page {element.page_start}"
        )
        print(f"Text: {element.text[:150]}")
        print(f"Section: {element.section_path}")
        print(
            f"Confidence: "
            f"{element.metadata['structure']['confidence']}"
        )
        print()

    print("PASS: Element count preserved")
    print("PASS: Document metadata preserved")
    print("PASS: Structure metadata present")
    print("PASS: Heading inference")
    print("PASS: Structure inference completed")


if __name__ == "__main__":
    main()
