from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
)
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
)


def main():
    document = CanonicalDocument(
        title="NIST SP 800-53",
        elements=[
            DocumentElement(
                element_type=ElementType.HEADING,
                text="AU-9 PROTECTION OF AUDIT INFORMATION",
            ),
            DocumentElement(
                element_type=ElementType.PARAGRAPH,
                text="Control:",
            ),
            DocumentElement(
                element_type=ElementType.PARAGRAPH,
                text="The organization protects audit information.",
            ),
            DocumentElement(
                element_type=ElementType.PARAGRAPH,
                text="Discussion:",
            ),
            DocumentElement(
                element_type=ElementType.HEADING,
                text="AU-9(1) HARDWARE WRITE-ONCE MEDIA",
            ),
            DocumentElement(
                element_type=ElementType.PARAGRAPH,
                text="The organization protects audit information using hardware.",
            ),
            DocumentElement(
                element_type=ElementType.LIST,
                text="AC-2 ACCOUNT MANAGEMENT",
            ),
        ],
        page_count=1,
    )

    service = StructureInferenceService()
    result = service.infer(document)

    assert len(result.elements) == 7

    control = result.elements[0]
    assert control.metadata["structure"]["identifier"] == "AU-9"
    assert control.metadata["structure"]["structure_type"] == "control"
    assert control.metadata["structure"]["source"] == "nist.control"
    assert control.metadata["structure"]["parent_identifier"] is None

    control_text = result.elements[1]
    assert control_text.metadata["structure"]["identifier"] == "control"

    discussion = result.elements[3]
    assert discussion.metadata["structure"]["identifier"] == "discussion"

    enhancement = result.elements[4]
    assert enhancement.metadata["structure"]["identifier"] == "AU-9(1)"
    assert enhancement.metadata["structure"]["structure_type"] == "control_enhancement"
    assert enhancement.metadata["structure"]["parent_identifier"] == "AU-9"

    ac2 = result.elements[6]

    assert ac2.metadata["structure"]["identifier"] == "AC-2"
    assert ac2.metadata["structure"]["structure_type"] == "control"
    assert ac2.metadata["structure"]["source"] == "nist.control"

    print("[PASS] NIST control detection")
    print("[PASS] NIST control enhancement detection")
    print("[PASS] NIST content role detection")
    print("[PASS] Structure metadata preserved")
    print("[PASS] NIST structure test completed")


if __name__ == "__main__":
    main()
