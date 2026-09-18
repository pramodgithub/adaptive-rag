from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import DocumentElement
from services.ingestion.structure.gdpr_strategy import GDPRStructureStrategy

from .generic_strategy import GenericStructureStrategy
from .models import InferredStructure
from .nist_strategy import NISTStructureStrategy
from .strategy import StructureStrategy


class StructureInferenceService:
    def __init__(
        self,
        strategies: list[StructureStrategy] | None = None,
    ):
        self.strategies = strategies or [
            NISTStructureStrategy(),
            GDPRStructureStrategy(),
            GenericStructureStrategy(),
        ]

    def infer(
        self,
        document: CanonicalDocument,
    ) -> CanonicalDocument:
        current_path: list[str] = []
        elements: list[DocumentElement] = []

        for element in document.elements:
            previous_elements = elements

            structure = self._infer(
                element=element,
                previous_elements=previous_elements,
                current_path=current_path,
            )

            if structure is not None:
                current_path = structure.section_path

            metadata = dict(element.metadata)

            if structure is not None:
                metadata["structure"] = {
                    "section_path": structure.section_path,
                    "confidence": structure.confidence,
                    "source": structure.source,
                    "structure_type": structure.structure_type,
                    "identifier": structure.identifier,
                    "parent_identifier": structure.parent_identifier,
                }

                section_path = structure.section_path
            else:
                metadata["structure"] = {
                    "section_path": current_path,
                    "confidence": 0.0,
                    "source": "none",
                    "structure_type": None,
                    "identifier": None,
                    "parent_identifier": None,
                }

                section_path = current_path

            elements.append(
                DocumentElement(
                    element_type=element.element_type,
                    text=element.text,
                    page_start=element.page_start,
                    page_end=element.page_end,
                    section_path=list(section_path),
                    metadata=metadata,
                    table=element.table,
                )
            )

        return CanonicalDocument(
            title=document.title,
            elements=elements,
            page_count=document.page_count,
            metadata=dict(document.metadata),
        )

    def _infer(
        self,
        element: DocumentElement,
        previous_elements: list[DocumentElement],
        current_path: list[str],
    ) -> InferredStructure | None:

        for strategy in self.strategies:
            result = strategy.infer(
                element=element,
                previous_elements=previous_elements,
                current_path=current_path,
            )

            if result is not None:
                return result

        return None
