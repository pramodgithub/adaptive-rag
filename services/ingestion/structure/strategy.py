from abc import ABC, abstractmethod

from services.ingestion.domain.elements import DocumentElement

from .models import InferredStructure


class StructureStrategy(ABC):
    @abstractmethod
    def infer(
        self,
        element: DocumentElement,
        previous_elements: list[DocumentElement],
        current_path: list[str],
    ) -> InferredStructure | None:
        raise NotImplementedError
