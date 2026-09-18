import re

from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import DocumentElement


class DocumentNormalizer:
    PAGE_SEPARATOR_PATTERN = re.compile(r"^[\s_]{20,}$")

    def normalize(self, document: CanonicalDocument) -> CanonicalDocument:
        normalized_elements: list[DocumentElement] = []

        for element in document.elements:
            text = self._normalize_text(element.text)

            if self._is_noise(element, text):
                continue

            normalized_elements.append(
                DocumentElement(
                    element_type=element.element_type,
                    text=text,
                    page_start=element.page_start,
                    page_end=element.page_end,
                    section_path=list(element.section_path),
                    metadata=dict(element.metadata),
                    table=element.table,
                )
            )

        return CanonicalDocument(
            title=self._normalize_text(document.title),
            elements=normalized_elements,
            page_count=document.page_count,
            metadata=dict(document.metadata),
        )

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        if not text:
            return ""

        text = text.replace("\u00a0", " ")
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    @classmethod
    def _is_noise(
        cls,
        element: DocumentElement,
        text: str,
    ) -> bool:
        if not text:
            return element.element_type.value != "image"

        if cls.PAGE_SEPARATOR_PATTERN.match(text):
            return True

        return False
