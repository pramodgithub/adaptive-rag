from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import DocumentElement, ElementType

from .generic_strategy import GenericStructureStrategy
from .models import InferredStructure
from .strategy import StructureStrategy


class StructureInferenceService:
    def __init__(
        self,
        strategy: StructureStrategy | None = None,
    ):
        self.strategy = strategy or GenericStructureStrategy()

    def infer(self, document: CanonicalDocument) -> CanonicalDocument:
        current_path: list[str] = []
        current_identifier: str | None = None
        current_parent_identifier: str | None = None
        current_structure_type: str | None = None

        elements: list[DocumentElement] = []

        for element in document.elements:
            structure = self.strategy.infer(
                element=element,
                previous_elements=elements,
                current_path=current_path,
            )

            metadata = dict(element.metadata)
            existing_structure = metadata.get("structure", {})

            if not isinstance(existing_structure, dict):
                existing_structure = {}
            else:
                existing_structure = dict(existing_structure)

            if structure is not None:
                current_path = list(structure.section_path)

                # A title starts a new document-level scope.
                if element.element_type == ElementType.TITLE:
                    current_identifier = None
                    current_parent_identifier = None
                    current_structure_type = None

                # A recognized structural heading establishes a new identity.
                elif structure.identifier:
                    current_identifier = structure.identifier
                    current_parent_identifier = structure.parent_identifier
                    current_structure_type = structure.structure_type

                inferred_structure = {
                    "section_path": list(structure.section_path),
                    "confidence": structure.confidence,
                    "source": structure.source,
                    "structure_type": structure.structure_type,
                    "identifier": structure.identifier,
                    "parent_identifier": structure.parent_identifier,
                }

                merged_structure = dict(existing_structure)

                for key, value in inferred_structure.items():
                    if value is not None:
                        merged_structure[key] = value

                # Carry the active structural identity onto headings and body
                # elements that do not establish a new identified structure.
                if (
                    element.element_type != ElementType.TITLE
                    and not structure.identifier
                    and current_identifier
                ):
                    merged_structure["identifier"] = current_identifier
                    merged_structure["parent_identifier"] = (
                        current_parent_identifier
                    )
                    merged_structure["structure_type"] = current_structure_type

                merged_structure["section_path"] = list(structure.section_path)
                metadata["structure"] = merged_structure
                section_path = list(structure.section_path)

            else:
                merged_structure = dict(existing_structure)
                merged_structure.setdefault("section_path", list(current_path))
                merged_structure.setdefault("confidence", 0.0)
                merged_structure.setdefault("source", "none")

                if current_identifier:
                    merged_structure["identifier"] = current_identifier
                    merged_structure["parent_identifier"] = (
                        current_parent_identifier
                    )
                    merged_structure["structure_type"] = current_structure_type
                else:
                    merged_structure.setdefault("structure_type", None)
                    merged_structure.setdefault("identifier", None)
                    merged_structure.setdefault("parent_identifier", None)

                metadata["structure"] = merged_structure
                section_path = list(merged_structure["section_path"])

            elements.append(
                DocumentElement(
                    element_type=element.element_type,
                    text=element.text,
                    page_start=element.page_start,
                    page_end=element.page_end,
                    section_path=section_path,
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
