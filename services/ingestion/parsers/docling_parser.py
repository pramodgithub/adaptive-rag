import re
from pathlib import Path
from typing import Any

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)
from docling_core.types.doc import (
    ContentLayer,
    DocItemLabel,
    SectionHeaderItem,
    TableItem,
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

        return self.parse_document(
            document=result.document,
            source_name=source.name,
        )

    def parse_document(
        self,
        document: Any,
        source_name: str,
    ) -> ParsedDocument:
        """Everything after conversion. Tests call this with a cached document.

        Note: this changes `document` in place (text normalization).
        """
        source = Path(source_name)

        self._normalize_docling_document(document)
        self._exclude_contents_tables(document)
        self._exclude_contents_section(document)
        promoted_refs = self._promote_missed_headings(document)
        joined_refs = self._join_number_and_title(document)
        level_source = self._assign_heading_levels(document)
        continued_refs = self._carry_headers_to_continued_tables(document)

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
                if element.metadata.get("source_ref") in promoted_refs:
                    element.metadata["promoted_heading"] = True

                if element.metadata.get("source_ref") in joined_refs:
                    element.metadata["joined_title"] = True

                if element.metadata.get("source_ref") in continued_refs:
                    element.metadata["continued_table"] = True

                if element.element_type == ElementType.HEADING:
                    element.metadata["heading_level"] = getattr(
                        item, "level", None
                    )
                    element.metadata["heading_level_source"] = level_source

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

    @classmethod
    def _normalize_docling_document(
        cls,
        document: Any,
    ) -> None:
        # The chunks are built from this document, so it gets the same
        # cleanup as the elements: hidden marks out, spaces tidied.
        for item in getattr(document, "texts", []):
            text = getattr(item, "text", None)

            if text:
                text = normalize_text(text)
                label = getattr(getattr(item, "label", None), "value", None)

                if label != "code":
                    text = cls._clean_text(text)

                item.text = text

        for table in getattr(document, "tables", []):
            data = getattr(table, "data", None)

            if data is None:
                continue

            for cell in getattr(data, "table_cells", []):
                text = getattr(cell, "text", None)

                if text:
                    cell.text = cls._clean_text(normalize_text(text))

    @staticmethod
    def _exclude_contents_tables(
        document: Any,
    ) -> None:
        # A table of contents only repeats headings. Moving it out of the
        # body layer keeps it out of both the elements and the chunks.
        for table in getattr(document, "tables", []):
            label = getattr(getattr(table, "label", None), "value", None)

            if label == "document_index":
                table.content_layer = ContentLayer.FURNITURE

    _CONTENTS_HEADING = re.compile(
        r"^\s*(table\s+of\s+)?contents\s*$",
        re.IGNORECASE,
    )

    @classmethod
    def _exclude_contents_section(
        cls,
        document: Any,
    ) -> None:
        # Docling doesn't always label a contents page. So also treat
        # everything under a "Contents" / "Table of Contents" heading, up
        # to the next heading, as a contents page and move it out.
        in_contents = False

        for item, _ in document.iterate_items():
            text = (getattr(item, "text", "") or "").strip()
            is_heading = isinstance(item, SectionHeaderItem)

            if text and len(text) <= 40 and cls._CONTENTS_HEADING.match(text):
                in_contents = True
                item.content_layer = ContentLayer.FURNITURE
                continue

            if is_heading:
                in_contents = False
                continue

            if in_contents:
                item.content_layer = ContentLayer.FURNITURE

    # Numbering that starts a section in compliance documents
    # (regulations, standards, audit reports, policies).
    _HEADING_PATTERN = re.compile(
        r"^(Article|Section|Clause|Chapter|Part|Annex|Appendix|Schedule)"
        r"\s+[\dIVXLC]+\b"
        r"|^(CC|A\.|PI|C|P)\d+(\.\d+)+\b"
        r"|^\d+(\.\d+)+\s+\S",
        re.IGNORECASE,
    )
    _HEADING_MAX_CHARS = 120

    @classmethod
    def _promote_missed_headings(
        cls,
        document: Any,
    ) -> set[str]:
        # Docling sometimes tags a heading such as "Article 7" as plain
        # text. Turning it into a real heading in the Docling document
        # makes both the elements and the chunk boundaries see it.
        promoted: set[str] = set()

        for index, item in enumerate(getattr(document, "texts", [])):
            label = getattr(getattr(item, "label", None), "value", None)

            if label not in ("text", "paragraph"):
                continue

            if getattr(item, "content_layer", None) != ContentLayer.BODY:
                continue

            text = (getattr(item, "text", "") or "").strip()

            if (
                not text
                or len(text) > cls._HEADING_MAX_CHARS
                or text.endswith((".", ";", ","))
                or not cls._HEADING_PATTERN.match(text)
            ):
                continue

            fields = {
                name: getattr(item, name)
                for name in SectionHeaderItem.model_fields
                if name not in ("label", "level") and hasattr(item, name)
            }

            document.texts[index] = SectionHeaderItem(
                **fields,
                label=DocItemLabel.SECTION_HEADER,
                level=1,
            )
            promoted.add(item.self_ref)

        return promoted

    # Rank of each numbering style, highest first. Only the styles a
    # document actually uses are kept, so its top style becomes level 1.
    _KEYWORD_RANK = {
        "part": 0,
        "chapter": 1, "annex": 1, "appendix": 1, "schedule": 1,
        "section": 2,
        "article": 3, "clause": 3,
    }
    _KEYWORD_NUMBER = re.compile(
        r"^(part|chapter|annex|appendix|schedule|section|article|clause)"
        r"\s+([\dIVXLC]+[a-z]?)\b",
        re.IGNORECASE,
    )
    _DOTTED_NUMBER = re.compile(
        r"^(?:CC|A\.|PI|C|P)?(\d+(?:\.\d+)*)(?=\s+\S|$)",
        re.IGNORECASE,
    )

    @classmethod
    def _heading_rank(
        cls,
        text: str,
    ) -> int | None:
        text = text.strip()

        match = cls._KEYWORD_NUMBER.match(text)
        if match:
            return cls._KEYWORD_RANK[match.group(1).lower()]

        match = cls._DOTTED_NUMBER.match(text)
        if match:
            # "5" -> 4, "5.1" -> 5, "5.1.2" -> 6
            return 4 + match.group(1).count(".")

        return None

    @classmethod
    def _is_number_only(
        cls,
        text: str,
    ) -> bool:
        # "Article 7", "CHAPTER III", "Section 2" with no title after it.
        text = text.strip().rstrip(".:")
        match = cls._KEYWORD_NUMBER.match(text) or cls._DOTTED_NUMBER.match(text)
        return bool(match) and match.end() >= len(text)

    @classmethod
    def _join_number_and_title(
        cls,
        document: Any,
    ) -> set[str]:
        # "Article 7" followed by the heading "Conditions for consent"
        # becomes one heading: "Article 7: Conditions for consent".
        # The separate title is moved out of the body.
        joined: set[str] = set()
        items = [item for item, _ in document.iterate_items()]

        for current, following in zip(items, items[1:]):
            if not isinstance(current, SectionHeaderItem):
                continue

            if not isinstance(following, SectionHeaderItem):
                continue

            if not cls._is_number_only(current.text):
                continue

            if cls._heading_rank(following.text) is not None:
                continue

            current.text = f"{current.text.strip().rstrip('.:')}: {following.text.strip()}"
            following.content_layer = ContentLayer.FURNITURE
            joined.add(current.self_ref)

        return joined

    @classmethod
    def _assign_heading_levels(
        cls,
        document: Any,
    ) -> str:
        headings = [
            item for item, _ in document.iterate_items()
            if isinstance(item, SectionHeaderItem)
        ]

        if not headings:
            return "none"

        # Word, HTML and Markdown files usually come with real levels.
        if len({heading.level for heading in headings}) > 1:
            return "docling"

        ranks = [cls._heading_rank(heading.text) for heading in headings]
        used = sorted({rank for rank in ranks if rank is not None})

        if not used:
            return "docling"

        level_of_rank = {rank: index + 1 for index, rank in enumerate(used)}
        last_numbered_level = 0

        for heading, rank in zip(headings, ranks):
            if rank is not None:
                heading.level = level_of_rank[rank]
                last_numbered_level = heading.level
            else:
                # Unnumbered heading: one level below the section it sits in.
                heading.level = last_numbered_level + 1

        return "numbering"

    @staticmethod
    def _header_rows(
        table: Any,
    ) -> list[int]:
        cells = getattr(getattr(table, "data", None), "table_cells", None) or []
        return sorted({
            row
            for cell in cells
            if cell.column_header
            for row in range(cell.start_row_offset_idx, cell.end_row_offset_idx)
        })

    @staticmethod
    def _first_page(
        item: Any,
    ) -> int | None:
        provenance = getattr(item, "prov", None) or []
        return provenance[0].page_no if provenance else None

    @classmethod
    def _carry_headers_to_continued_tables(
        cls,
        document: Any,
    ) -> set[str]:
        # Docling splits a long table into one table per page, and only
        # the first part has the header. A table with no header, on the
        # page right after a table with the same columns, is treated as
        # its continuation and gets that header copied on top.
        continued: set[str] = set()
        previous = None

        for item, _ in document.iterate_items():
            if not isinstance(item, TableItem):
                continue

            data = getattr(item, "data", None)

            if data is None or not data.table_cells:
                previous = item
                continue

            if (
                previous is not None
                and not cls._header_rows(item)
                and getattr(previous.data, "num_cols", None) == data.num_cols
            ):
                previous_page = cls._first_page(previous)
                page = cls._first_page(item)
                header = cls._header_rows(previous)
                header_height = len(header)

                if (
                    previous_page is not None
                    and page == previous_page + 1
                    and header == list(range(header_height))
                    and header_height > 0
                ):
                    header_cells = [
                        cell.model_copy(update={"bbox": None})
                        for cell in previous.data.table_cells
                        if cell.start_row_offset_idx < header_height
                    ]
                    body_cells = [
                        cell.model_copy(update={
                            "start_row_offset_idx": cell.start_row_offset_idx + header_height,
                            "end_row_offset_idx": cell.end_row_offset_idx + header_height,
                        })
                        for cell in data.table_cells
                    ]
                    data.table_cells = header_cells + body_cells
                    data.num_rows += header_height
                    continued.add(item.self_ref)

            previous = item

        return continued

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

    # Docling's own label says what an item is. Class names can't:
    # footnotes, captions and paragraphs are all the same class.
    _LABEL_TO_TYPE = {
        "title": ElementType.TITLE,
        "section_header": ElementType.HEADING,
        "list_item": ElementType.LIST,
        "table": ElementType.TABLE,
        "document_index": ElementType.TABLE,
        "picture": ElementType.IMAGE,
        "chart": ElementType.IMAGE,
        "footnote": ElementType.FOOTNOTE,
        "text": ElementType.PARAGRAPH,
        "paragraph": ElementType.PARAGRAPH,
        "caption": ElementType.PARAGRAPH,
        "code": ElementType.PARAGRAPH,
        "formula": ElementType.PARAGRAPH,
        "reference": ElementType.PARAGRAPH,
    }

    @classmethod
    def _detect_element_type(
        cls,
        item: Any,
    ) -> ElementType:
        label = getattr(getattr(item, "label", None), "value", None)

        if label in cls._LABEL_TO_TYPE:
            return cls._LABEL_TO_TYPE[label]

        # Fallback for labels not listed above.
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

        # Header rows are the ones Docling marked. No marks = no header.
        header_rows = set(cls._header_rows(item))

        if header_rows:
            headers = []
            for column in range(len(rows[0])):
                parts: list[str] = []
                for index in sorted(header_rows):
                    if index < len(rows) and column < len(rows[index]):
                        value = rows[index][column]
                        if value and value not in parts:
                            parts.append(value)
                headers.append(" / ".join(parts))
        else:
            headers = []

        body_rows = [
            row
            for index, row in enumerate(rows)
            if index not in header_rows
        ]

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