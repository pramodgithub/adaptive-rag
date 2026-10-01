from pathlib import Path
from typing import Any

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)
from transformers import AutoTokenizer

from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
    TableData,
)
from services.ingestion.normalization.text_normalizer import normalize_text
from services.ingestion.parsers.parsed_document import ParsedDocument

from .base import DocumentParser
from .chunk_candidate import ChunkCandidate


class DoclingParser(DocumentParser):
    def __init__(self):
        self.converter = DocumentConverter()

        tokenizer = AutoTokenizer.from_pretrained(
            "google/gemma-2-9b-it"
        )

        self.chunk_tokenizer = HuggingFaceTokenizer(
            tokenizer=tokenizer,
            max_tokens=512,
        )

        self.chunker = HybridChunker(
            tokenizer=self.chunk_tokenizer,
            repeat_table_header=True,
            merge_peers=True,
            always_emit_headings=False,
        )

    def parse(
        self,
        file_path: str,
        **kwargs,
    ) -> ParsedDocument:
        source = Path(file_path)

        result = self.converter.convert(
            source,
            **kwargs,
        )

        document = result.document

        self._normalize_docling_document(document)

        chunk_candidates = self._build_chunk_candidates(
            document
        )

        elements: list[DocumentElement] = []

        for item, level in document.iterate_items():
            element = self._convert_item(
                item=item,
                level=level,
            )

            if element is not None:
                elements.append(element)

        return ParsedDocument(
            canonical=CanonicalDocument(
                title=self._clean_text(source.name),
                elements=elements,
                page_count=self._get_page_count(document),
                metadata={
                    "source_format": source.suffix.lower().lstrip("."),
                    "parser": "docling",
                    "parser_version": "2.126.0",
                },
            ),
            docling_document=document,
            chunk_candidates=chunk_candidates,
        )

    @staticmethod
    def _normalize_docling_document(
        document: Any,
    ) -> None:
        for item in getattr(document, "texts", []):
            text = getattr(item, "text", None)

            if text:
                item.text = normalize_text(text)

        for table in getattr(document, "tables", []):
            data = getattr(table, "data", None)

            if data is None:
                continue

            for cell in getattr(data, "table_cells", []):
                text = getattr(cell, "text", None)

                if text:
                    cell.text = normalize_text(text)

    def _build_chunk_candidates(
        self,
        document: Any,
    ) -> list[ChunkCandidate]:
        candidates: list[ChunkCandidate] = []

        for chunk in self.chunker.chunk(document):
            text = self.chunker.contextualize(
                chunk
            ).strip()

            if not text:
                continue

            source_refs: list[str] = []
            pages: list[int] = []

            for item in getattr(
                chunk.meta,
                "doc_items",
                [],
            ):
                source_ref = getattr(
                    item,
                    "self_ref",
                    None,
                )

                if source_ref:
                    source_refs.append(source_ref)

                for provenance in getattr(
                    item,
                    "prov",
                    [],
                ):
                    page_no = getattr(
                        provenance,
                        "page_no",
                        None,
                    )

                    if page_no is not None:
                        pages.append(page_no)

            headings = list(
                getattr(
                    chunk.meta,
                    "headings",
                    [],
                )
                or []
            )

            candidates.append(
                ChunkCandidate(
                    text=text,
                    source_refs=source_refs,
                    page_start=min(pages) if pages else None,
                    page_end=max(pages) if pages else None,
                    headings=headings,
                )
            )

        return candidates

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
                "source_ref": getattr(
                    item,
                    "self_ref",
                    None,
                ),
                "parent_ref": self._extract_parent_ref(
                    item
                ),
            },
        )

    @classmethod
    def _extract_text(
        cls,
        item: Any,
    ) -> str:
        text = getattr(item, "text", None)

        if not isinstance(text, str):
            return ""

        return cls._clean_text(text)

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:
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
            text = text.replace(
                source,
                replacement,
            )

        return " ".join(text.split()).strip()

    @staticmethod
    def _detect_element_type(
        item: Any,
    ) -> ElementType:
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
                    str(
                        getattr(
                            cell,
                            "text",
                            "",
                        )
                        or ""
                    )
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
                "source_ref": getattr(
                    item,
                    "self_ref",
                    None,
                ),
                "parent_ref": cls._extract_parent_ref(
                    item
                ),
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
                "source_ref": getattr(
                    item,
                    "self_ref",
                    None,
                ),
                "parent_ref": cls._extract_parent_ref(
                    item
                ),
            },
        )

    @staticmethod
    def _extract_parent_ref(
        item: Any,
    ) -> str | None:
        parent = getattr(
            item,
            "parent",
            None,
        )

        if parent is None:
            return None

        return getattr(
            parent,
            "cref",
            None,
        )

    @staticmethod
    def _extract_page_number(
        item: Any,
    ) -> int | None:
        provenance = getattr(
            item,
            "prov",
            None,
        )

        if not provenance:
            return None

        return getattr(
            provenance[0],
            "page_no",
            None,
        )

    @staticmethod
    def _get_page_count(
        document: Any,
    ) -> int:
        pages = getattr(
            document,
            "pages",
            None,
        )

        if pages is None:
            return 0

        return len(pages)
