import re

from services.ingestion.domain.elements import DocumentElement
from .models import InferredStructure
from .strategy import StructureStrategy


class NISTStructureStrategy(StructureStrategy):
    CONTROL_PATTERN = re.compile(
        r"^(?P<identifier>[A-Z]{2}-\d+)(?P<enhancement>\(\d+\))?\s+(?P<title>.+)$"
    )

    ROLE_MARKERS = {
        "Control:",
        "Discussion:",
        "Related Controls:",
        "Control Enhancements:",
    }

    def infer(
        self,
        element: DocumentElement,
        previous_elements: list[DocumentElement],
        current_path: list[str],
    ) -> InferredStructure | None:

        text = element.text.strip()

        if not text:
            return None

        control_match = self.CONTROL_PATTERN.match(text)

        if control_match:
            identifier = control_match.group("identifier")
            enhancement = control_match.group("enhancement")

            if enhancement:
                structure_type = "control_enhancement"
                full_identifier = f"{identifier}{enhancement}"
                parent_identifier = identifier
            else:
                structure_type = "control"
                full_identifier = identifier
                parent_identifier = None

            return InferredStructure(
                section_path=[text],
                confidence=0.98,
                source="nist.control",
                structure_type=structure_type,
                identifier=full_identifier,
                parent_identifier=parent_identifier,
            )

        if text in self.ROLE_MARKERS:
            return InferredStructure(
                section_path=list(current_path),
                confidence=0.95,
                source="nist.role",
                structure_type="content_role",
                identifier=text.rstrip(":").lower().replace(" ", "_"),
            )

        return None
