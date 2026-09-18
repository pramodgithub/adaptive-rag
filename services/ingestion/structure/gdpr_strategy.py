import re

from services.ingestion.domain.elements import DocumentElement, ElementType
from .models import InferredStructure
from .strategy import StructureStrategy


class GDPRStructureStrategy(StructureStrategy):
    ARTICLE_PATTERN = re.compile(
        r"^Article\s+(?P<identifier>\d+)\s*(?P<title>.*)$",
        re.IGNORECASE,
    )

    RECITAL_PATTERN = re.compile(
        r"^Recital\s+(?P<identifier>\d+)\s*(?P<title>.*)$",
        re.IGNORECASE,
    )

    def infer(self, element, previous_elements, current_path):
        text = element.text.strip()

        if not text:
            return None

        article_match = self.ARTICLE_PATTERN.match(text)
        if article_match:
            identifier = article_match.group("identifier")

            return InferredStructure(
                section_path=[text],
                confidence=0.98,
                source="gdpr.article",
                structure_type="article",
                identifier=identifier,
            )

        recital_match = self.RECITAL_PATTERN.match(text)
        if recital_match:
            identifier = recital_match.group("identifier")

            return InferredStructure(
                section_path=[text],
                confidence=0.98,
                source="gdpr.recital",
                structure_type="recital",
                identifier=identifier,
            )

        if (
            element.element_type == ElementType.HEADING
            and previous_elements
            and current_path
        ):
            previous = previous_elements[-1]
            previous_structure = previous.metadata.get("structure", {})

            if previous_structure.get("structure_type") == "article":
                return InferredStructure(
                    section_path=list(current_path),
                    confidence=0.95,
                    source="gdpr.article_title",
                    structure_type="article_title",
                    identifier=previous_structure.get("identifier"),
                    parent_identifier=previous_structure.get("identifier"),
                )

        return None
