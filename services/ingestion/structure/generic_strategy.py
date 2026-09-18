from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
)

from .models import InferredStructure
from .strategy import StructureStrategy


class GenericStructureStrategy(StructureStrategy):
    def infer(
        self,
        element: DocumentElement,
        previous_elements: list[DocumentElement],
        current_path: list[str],
    ) -> InferredStructure | None:
        if element.element_type == ElementType.TITLE:
            return InferredStructure(
                section_path=[],
                confidence=1.0,
                source="generic.title",
            )

        if element.element_type == ElementType.HEADING:
            return InferredStructure(
                section_path=[element.text],
                confidence=0.95,
                source="generic.heading",
            )

        if current_path:
            return InferredStructure(
                section_path=list(current_path),
                confidence=0.5,
                source="generic.inherited",
            )

        return None
