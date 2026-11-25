from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
)
from services.ingestion.structure.structure_inference import StructureInferenceService


class NoStructureStrategy:
    def infer(self, element, previous_elements, current_path):
        return None


def test_infer_preserves_existing_structure_when_strategy_returns_none():
    print("\n========== STRUCTURE INFERENCE TEST ==========", flush=True)

    element = DocumentElement(
        element_type=ElementType.PARAGRAPH,
        text="Administrators must use multi-factor authentication.",
        section_path=["Access Management"],
        metadata={
            "source_ref": "#/texts/10",
            "structure": {
                "section_path": ["Access Management"],
                "confidence": 0.9,
                "source": "parser",
                "structure_type": "control",
                "identifier": "AC-01",
                "parent_identifier": "AC",
            },
        },
    )

    document = CanonicalDocument(
        title="Test document",
        elements=[element],
        page_count=1,
        metadata={},
    )

    print("BEFORE INFERENCE:", flush=True)
    print("  source_ref:", element.metadata.get("source_ref"), flush=True)
    print("  structure:", element.metadata.get("structure"), flush=True)

    service = StructureInferenceService(
        strategy=NoStructureStrategy(),
    )

    result = service.infer(document)

    inferred_element = result.elements[0]
    structure = inferred_element.metadata["structure"]

    print("\nAFTER INFERENCE:", flush=True)
    print("  source_ref:", inferred_element.metadata.get("source_ref"), flush=True)
    print("  section_path:", inferred_element.section_path, flush=True)
    print("  structure:", structure, flush=True)

    assert structure["identifier"] == "AC-01"
    assert structure["parent_identifier"] == "AC"
    assert structure["structure_type"] == "control"
    assert structure["section_path"] == ["Access Management"]
    assert inferred_element.metadata["source_ref"] == "#/texts/10"

    print("\nRESULT: PASS — existing structure was preserved.", flush=True)


if __name__ == "__main__":
    test_infer_preserves_existing_structure_when_strategy_returns_none()
