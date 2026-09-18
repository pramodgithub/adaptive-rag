from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter

from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
    TableData,
)

from .base import DocumentParser


class DoclingParser(DocumentParser):
    def __init__(self):
        self.converter = DocumentConverter()

    def parse(self, file_path: str, **kwargs) -> CanonicalDocument:
        source = Path(file_path)
        result = self.converter.convert(source, **kwargs)
        document = result.document

        elements: list[DocumentElement] = []

        for item, level in document.iterate_items():
            element = self._convert_item(
                item=item,
                level=level,
            )

            if element is not None:
                elements.append(element)

        return CanonicalDocument(
            title=self._clean_text(source.name),
            elements=elements,
            page_count=self._get_page_count(document),
            metadata={
                "source_format": source.suffix.lower().lstrip("."),
                "parser": "docling",
                "parser_version": "2.126.0",
            },
        )

    def _convert_item(
        self,
        item: Any,
        level: int,
    ) -> DocumentElement | None:
        element_type = self._detect_element_type(item)

        if element_type == ElementType.TABLE:
            return self._convert_table(item, level)

        if element_type == ElementType.IMAGE:
            return self._convert_image(item, level)

        text = self._extract_text(item)

        if not text:
            return None

        page_number = self._extract_page_number(item)

        return DocumentElement(
            element_type=element_type,
            text=text,
            page_start=page_number,
            page_end=page_number,
            metadata={
                "docling_level": level,
                "source_ref": getattr(item, "self_ref", None),
                "parent_ref": self._extract_parent_ref(item),
            },
        )

    @classmethod
    def _extract_text(cls, item: Any) -> str:
        text = getattr(item, "text", None)

        if not isinstance(text, str):
            return ""

        return cls._clean_text(text)

    @staticmethod
    def _clean_text(text: str) -> str:
        replacements = {
            "\u202a": "",
            "\u202b": "",
            "\u202c": "",
            "\u202d": "",
            "\u202e": "",
            "\u2066": "",
            "\u2067": "",
            "\u2068": "",
            "\u2069": "",
        }

        for source, replacement in replacements.items():
            text = text.replace(source, replacement)

        return " ".join(text.split()).strip()

    @staticmethod
    def _detect_element_type(item: Any) -> ElementType:
        name = item.__class__.__name__.lower()

        if "title" in name:
            return ElementType.TITLE

        if "sectionheader" in name or "heading" in name:
            return ElementType.HEADING

        if "table" in name:
            return ElementType.TABLE

        if "list" in name:
            return ElementType.LIST

        if "picture" in name or "image" in name:
            return ElementType.IMAGE

        if "footnote" in name:
            return ElementType.FOOTNOTE

        if "text" in name or "paragraph" in name:
            return ElementType.PARAGRAPH

        return ElementType.UNKNOWN

    @classmethod
    def _convert_table(
        cls,
        item: Any,
        level: int,
    ) -> DocumentElement | None:
        table_data = getattr(item, "data", None)

        if table_data is None:
            return None

        grid = getattr(table_data, "grid", None)

        if not grid:
            return None

        rows: list[list[str]] = []

        for row in grid:
            values = [
                cls._clean_text(
                    str(getattr(cell, "text", "") or "")
                )
                for cell in row
            ]

            rows.append(values)

        if not rows:
            return None

        headers = rows[0]
        body_rows = rows[1:]

        text = "\n".join(
            " | ".join(row)
            for row in rows
        )

        if not text.strip():
            return None

        page_number = cls._extract_page_number(item)

        return DocumentElement(
            element_type=ElementType.TABLE,
            text=text,
            page_start=page_number,
            page_end=page_number,
            metadata={
                "docling_level": level,
                "source_ref": getattr(item, "self_ref", None),
                "parent_ref": cls._extract_parent_ref(item),
            },
            table=TableData(
                headers=headers,
                rows=body_rows,
            ),
        )

    @classmethod
    def _convert_image(
        cls,
        item: Any,
        level: int,
    ) -> DocumentElement:
        page_number = cls._extract_page_number(item)

        return DocumentElement(
            element_type=ElementType.IMAGE,
            text="",
            page_start=page_number,
            page_end=page_number,
            metadata={
                "docling_level": level,
                "source_ref": getattr(item, "self_ref", None),
                "parent_ref": cls._extract_parent_ref(item),
            },
        )

    @staticmethod
    def _extract_parent_ref(item: Any) -> str | None:
        parent = getattr(item, "parent", None)

        if parent is None:
            return None

        return getattr(parent, "cref", None)

    @staticmethod
    def _extract_page_number(item: Any) -> int | None:
        provenance = getattr(item, "prov", None)

        if not provenance:
            return None

        return getattr(provenance[0], "page_no", None)

    @staticmethod
    def _get_page_count(document: Any) -> int:
        pages = getattr(document, "pages", None)

        if pages is None:
            return 0

        return len(pages)
