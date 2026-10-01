import re

from services.ingestion.domain.elements import DocumentElement
from .models import InferredStructure
from .strategy import StructureStrategy


class SOC2StructureStrategy(StructureStrategy):
    CONTROL_PATTERN = re.compile(
        r"^(?P<identifier>(?:CC|A)\d+(?:\.\d+)+)\s*:?\s*(?P<title>.*)$",
        re.IGNORECASE,
    )

    def infer(
        self,
        element: DocumentElement,
        previous_elements: list[DocumentElement],
        current_path: list[str],
    ) -> InferredStructure | None:
        text = element.text.strip()

        if not text:
            return None

        match = self.CONTROL_PATTERN.match(text)

        if not match:
            return None

        identifier = match.group("identifier").upper()

        return InferredStructure(
            section_path=[text],
            confidence=0.98,
            source="soc2.control",
            structure_type="control",
            identifier=identifier,
            parent_identifier=None,
        )
