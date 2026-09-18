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
        title="General Data Protection Regulation",
        elements=[
            DocumentElement(
                element_type=ElementType.HEADING,
                text="Recital 1",
            ),
            DocumentElement(
                element_type=ElementType.PARAGRAPH,
                text="The protection of natural persons...",
            ),
            DocumentElement(
                element_type=ElementType.HEADING,
                text="Article 5 Principles relating to processing",
            ),
            DocumentElement(
                element_type=ElementType.PARAGRAPH,
                text="Personal data shall be processed lawfully.",
            ),
            DocumentElement(
                element_type=ElementType.LIST,
                text="Article 32 Security of processing",
            ),
            DocumentElement(
                element_type=ElementType.PARAGRAPH,
                text="Taking into account the state of the art...",
            ),
        ],
        page_count=1,
    )

    service = StructureInferenceService()
    result = service.infer(document)

    assert len(result.elements) == 6

    recital = result.elements[0]
    assert recital.metadata["structure"]["identifier"] == "1"
    assert recital.metadata["structure"]["structure_type"] == "recital"
    assert recital.metadata["structure"]["source"] == "gdpr.recital"

    article_5 = result.elements[2]
    assert article_5.metadata["structure"]["identifier"] == "5"
    assert article_5.metadata["structure"]["structure_type"] == "article"
    assert article_5.metadata["structure"]["source"] == "gdpr.article"

    article_32 = result.elements[4]
    assert article_32.metadata["structure"]["identifier"] == "32"
    assert article_32.metadata["structure"]["structure_type"] == "article"

    print("[PASS] GDPR recital detection")
    print("[PASS] GDPR article detection")
    print("[PASS] GDPR article detection from ListItem")
    print("[PASS] Structure metadata preserved")
    print("[PASS] GDPR structure test completed")


if __name__ == "__main__":
    main()
