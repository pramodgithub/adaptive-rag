from services.ingestion.chunking.chunker import ComplianceChunker
from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
)


def structured(
    text: str,
    structure_type: str | None = None,
    identifier: str | None = None,
    parent_identifier: str | None = None,
):
    return DocumentElement(
        element_type=ElementType.PARAGRAPH,
        text=text,
        metadata={
            "structure": {
                "structure_type": structure_type,
                "identifier": identifier,
                "parent_identifier": parent_identifier,
            }
        },
    )


def main():
    document = CanonicalDocument(
        title="NIST Test",
        elements=[
            structured(
                "AC-2 ACCOUNT MANAGEMENT",
                "control",
                "AC-2",
            ),
            structured("Control:"),
            structured("The organization manages accounts."),
            structured("Discussion:"),
            structured("Accounts are reviewed periodically."),
            structured(
                "AC-2(1) AUTOMATED SYSTEM ACCOUNT MANAGEMENT",
                "control_enhancement",
                "AC-2(1)",
                "AC-2",
            ),
            structured("The organization automates account management."),
        ],
    )

    chunks = ComplianceChunker().chunk(document)

    assert len(chunks) == 2

    base = chunks[0]

    assert base.identifier == "AC-2"
    assert base.structure_type == "control"
    assert "The organization manages accounts." in base.text
    assert "Accounts are reviewed periodically." in base.text

    enhancement = chunks[1]

    assert enhancement.identifier == "AC-2(1)"
    assert enhancement.structure_type == "control_enhancement"
    assert enhancement.parent_identifier == "AC-2"
    assert "automates account management" in enhancement.text

    assert base.element_indexes == [0, 1, 2, 3, 4]
    assert enhancement.element_indexes == [5, 6]

    print("[PASS] Semantic control chunking")
    print("[PASS] Control enhancement chunking")
    print("[PASS] Parent identifier preserved")
    print("[PASS] Element traceability preserved")
    print("[PASS] Compliance chunker test completed")


if __name__ == "__main__":
    main()
