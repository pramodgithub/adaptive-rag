import re

from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
)

from .models import InferredStructure
from .strategy import StructureStrategy


class GenericStructureStrategy(StructureStrategy):
    # Structural identifiers, not arbitrary references in paragraph text.
    _IDENTIFIER_PATTERNS = (
        (
            "article",
            re.compile(
                r"^\s*Article\s+(\d+[a-z]?)"
                r"(?=$|[\s:.\-–—])",
                re.IGNORECASE,
            ),
        ),
        (
            "control",
            re.compile(
                r"^\s*(CC\d+(?:\.\d+)+)"
                r"(?=$|[\s:)\-–—])",
                re.IGNORECASE,
            ),
        ),
        (
            "numbered_section",
            re.compile(
                r"^\s*(\d+(?:\.\d+)+)"
                r"(?=$|[\s:)\-–—])",
            ),
        ),
        (
            "section",
            re.compile(
                r"^\s*(?:Section|Clause)\s+"
                r"(\d+(?:\.\d+)*(?:[a-z])?)"
                r"(?=$|[\s:.\-–—])",
                re.IGNORECASE,
            ),
        ),
    )

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
                structure_type="title",
            )

        if element.element_type == ElementType.HEADING:
            identifier, structure_type = self._extract_identifier(
                element.text
            )

            parent_identifier = None

            # A direct parent can be inferred from the preceding structural
            # heading only when the new heading extends its numbered path.
            if identifier:
                parent_identifier = self._resolve_parent_identifier(
                    identifier=identifier,
                    previous_elements=previous_elements,
                )

            return InferredStructure(
                section_path=(
                    [*current_path, element.text]
                    if parent_identifier
                    else [element.text]
                    if identifier
                    else [*current_path, element.text]
                ),
                confidence=0.95,
                source="generic.heading",
                structure_type=structure_type or "heading",
                identifier=identifier,
                parent_identifier=parent_identifier,
            )

        if current_path:
            return InferredStructure(
                section_path=list(current_path),
                confidence=0.5,
                source="generic.inherited",
            )

        return None

    @classmethod
    def _extract_identifier(
        cls,
        text: str,
    ) -> tuple[str | None, str | None]:
        for structure_type, pattern in cls._IDENTIFIER_PATTERNS:
            match = pattern.match(text)

            if match:
                identifier = match.group(1)

                # Normalize control identifiers consistently.
                if structure_type == "control":
                    identifier = identifier.upper()

                return identifier, structure_type

        return None, None

    @classmethod
    def _resolve_parent_identifier(
        cls,
        identifier: str,
        previous_elements: list[DocumentElement],
    ) -> str | None:
        # Parent inference is intentionally limited to dotted numeric
        # identifiers, where hierarchy is explicit in the identifier.
        if not re.fullmatch(r"\d+(?:\.\d+)+", identifier):
            return None

        parts = identifier.split(".")

        if len(parts) < 2:
            return None

        expected_parent = ".".join(parts[:-1])

        for previous in reversed(previous_elements):
            if previous.element_type != ElementType.HEADING:
                continue

            previous_structure = previous.metadata.get("structure", {})
            previous_identifier = (
                previous_structure.get("identifier")
                if isinstance(previous_structure, dict)
                else None
            )

            if previous_identifier == expected_parent:
                return expected_parent

        return None
