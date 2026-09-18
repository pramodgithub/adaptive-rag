from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
)

from .base import DocumentParser


class TextParser(DocumentParser):

    def parse(self, file_path: str) -> CanonicalDocument:
        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()

        return CanonicalDocument(
            title=file_path.rsplit("/", 1)[-1],
            elements=[
                DocumentElement(
                    element_type=ElementType.PARAGRAPH,
                    text=text,
                )
            ],
        )
