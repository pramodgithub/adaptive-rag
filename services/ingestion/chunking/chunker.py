from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import DocumentElement
from services.ingestion.parsers.chunk_candidate import ChunkCandidate

from .models import DocumentChunk
from .splitter import ChunkSizeSplitter
import re
import logging
logger = logging.getLogger(__name__)


class ComplianceChunker:
    def __init__(
        self,
        splitter: ChunkSizeSplitter | None = None,
    ):
        self.splitter = splitter or ChunkSizeSplitter()

    def chunk(
        self,
        document: CanonicalDocument,
        candidates: list[ChunkCandidate],
    ) -> list[DocumentChunk]:
        ref_to_index = {
            element.metadata["source_ref"]: index
            for index, element in enumerate(document.elements)
            if element.metadata.get("source_ref")
        }

        all_row_ids = self._collect_row_ids(document)
        rebuilt_tables: set[int] = set()
        chunks: list[DocumentChunk] = []

        for index, candidate in enumerate(candidates):
            table_rows = self._build_table_row_chunks(
                document=document,
                candidate=candidate,
                ref_to_index=ref_to_index,
                all_row_ids=all_row_ids,
                rebuilt_tables=rebuilt_tables,
            )

            if table_rows is not None:
                chunks.extend(table_rows)
                continue

            chunks.append(
                self._build_chunk(
                    document=document,
                    candidate=candidate,
                    chunk_index=index,
                    ref_to_index=ref_to_index,
                )
            )

        final_chunks: list[DocumentChunk] = []

        for chunk in chunks:
            final_chunks.extend(self.splitter.split(chunk))

        for index, chunk in enumerate(final_chunks):
            chunk.chunk_index = index

        return final_chunks

    # An ID at the start of a table's first cell: CC6.1.4, A.5.1, C1.1,
    # PI1.2, 8.3.1, AC-2, AC-2(1).
    _ROW_ID = re.compile(
        r"^\s*((?:[A-Z]{1,4}\.?)?\d+(?:\.\d+)+[a-z]?|[A-Z]{2}-\d+(?:\(\d+\))?)"
        r"(?=$|[\s:.,;)\-–—])"
    )
    _MIN_ID_ROWS = 2

    @classmethod
    def _row_id(cls, row: list[str]) -> str | None:
        if not row:
            return None

        match = cls._ROW_ID.match(row[0] or "")
        return match.group(1).upper() if match else None

    @classmethod
    def _collect_row_ids(cls, document: CanonicalDocument) -> set[str]:
        ids: set[str] = set()

        for element in document.elements:
            if element.table:
                for row in element.table.rows:
                    row_id = cls._row_id(row)
                    if row_id:
                        ids.add(row_id)

        return ids

    @staticmethod
    def _row_text(headers: list[str], row: list[str]) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()

        for column, value in enumerate(row):
            value = (value or "").strip()

            # Merged cells repeat the same text across columns.
            if not value or value in seen:
                continue

            seen.add(value)
            header = headers[column].strip() if column < len(headers) else ""
            lines.append(f"{header}: {value}" if header else value)

        return lines

    def _build_table_row_chunks(
        self,
        document: CanonicalDocument,
        candidate: ChunkCandidate,
        ref_to_index: dict[str, int],
        all_row_ids: set[str],
        rebuilt_tables: set[int],
    ) -> list[DocumentChunk] | None:
        """One chunk per ID row for tables like control matrices.

        Returns None when the candidate is not made only of ID tables,
        so it is chunked as before.
        """
        element_indexes = list(dict.fromkeys(
            ref_to_index[ref]
            for ref in candidate.source_refs
            if ref in ref_to_index
        ))

        if not element_indexes:
            return None

        tables = [document.elements[i] for i in element_indexes]

        if not all(element.table for element in tables):
            return None

        # Every table needs an ID row. Together they need two, unless the
        # table is a continuation the parser marked (a one-row tail of a
        # table split across pages).
        id_rows = [
            sum(1 for row in element.table.rows if self._row_id(row))
            for element in tables
        ]

        if min(id_rows) == 0:
            return None

        if sum(id_rows) < self._MIN_ID_ROWS and not any(
            element.metadata.get("continued_table") for element in tables
        ):
            return None

        section_path = (
            self._resolve_section_path(tables)
            or [h.strip() for h in candidate.headings if h.strip()]
        )
        base_structure = self._resolve_structure(
            elements=tables,
            text="",
            section_path=section_path,
        )
        heading_lines = [h.strip() for h in candidate.headings if h.strip()]
        chunks: list[DocumentChunk] = []

        for element_index, element in zip(element_indexes, tables):
            # A long table is split over several candidates. Rebuild it once.
            if element_index in rebuilt_tables:
                continue

            rebuilt_tables.add(element_index)
            groups: list[tuple[str | None, list[list[str]]]] = []

            for row in element.table.rows:
                row_id = self._row_id(row)

                if row_id or not groups:
                    groups.append((row_id, [row]))
                else:
                    groups[-1][1].append(row)

            for row_id, rows in groups:
                body: list[str] = []
                for row in rows:
                    body.extend(self._row_text(element.table.headers, row))

                if not body:
                    continue

                parent = None
                if row_id and "." in row_id:
                    prefix = row_id.rsplit(".", 1)[0]
                    if prefix in all_row_ids:
                        parent = prefix

                chunks.append(
                    DocumentChunk(
                        chunk_index=0,
                        text="\n".join([*heading_lines, *body]),
                        page_start=element.page_start,
                        page_end=element.page_end,
                        section_path=list(section_path),
                        structure_type="control" if row_id else base_structure["structure_type"],
                        identifier=row_id or base_structure["identifier"],
                        parent_identifier=(
                            parent or base_structure["identifier"]
                            if row_id
                            else base_structure["parent_identifier"]
                        ),
                        element_indexes=[element_index],
                        metadata={
                            "source": "table_rows",
                            "headings": candidate.headings,
                            "structural_identifiers": [row_id] if row_id else [],
                            "source_element_count": 1,
                            "unmatched_source_refs": [],
                            "table_row_count": len(rows),
                        },
                    )
                )

        return chunks

    def _build_chunk(
        self,
        document: CanonicalDocument,
        candidate: ChunkCandidate,
        chunk_index: int,
        ref_to_index: dict[str, int],
    ) -> DocumentChunk:
        element_indexes = list(
            dict.fromkeys(
                ref_to_index[ref]
                for ref in candidate.source_refs
                if ref in ref_to_index
            )
        )

        source_elements = [
            document.elements[index]
            for index in element_indexes
        ]

        section_path = (
            self._resolve_section_path(source_elements)
            or [
                heading.strip()
                for heading in candidate.headings
                if heading.strip()
            ]
        )

        structure = self._resolve_structure(
            elements=source_elements,
            text=candidate.text,
            section_path=section_path,
        )

        unmatched_refs = [
            ref
            for ref in candidate.source_refs
            if ref not in ref_to_index
        ]

        return DocumentChunk(
            chunk_index=chunk_index,
            text=candidate.text,
            page_start=candidate.page_start,
            page_end=candidate.page_end,
            section_path=section_path,
            structure_type=structure["structure_type"],
            identifier=structure["identifier"],
            parent_identifier=structure["parent_identifier"],
            element_indexes=element_indexes,
            metadata={
                "source": "hybrid_chunker",
                "headings": candidate.headings,
                "structural_identifiers": structure[
                    "structural_identifiers"
                ],
                "source_element_count": len(source_elements),
                "unmatched_source_refs": unmatched_refs,
            },
        )

    @staticmethod
    def _resolve_structure(
        elements: list[DocumentElement],
        text: str,
        section_path: list[str],
    ) -> dict:
        structures = [
            element.metadata.get("structure", {})
            for element in elements
        ]

        structures = [
            structure
            for structure in structures
            if isinstance(structure, dict) and structure
        ]

        inferred_identifiers = list(
            dict.fromkeys(
                structure["identifier"]
                for structure in structures
                if structure.get("identifier")
            )
        )

        parent_identifiers = list(
            dict.fromkeys(
                structure["parent_identifier"]
                for structure in structures
                if structure.get("parent_identifier")
            )
        )

        structure_types = list(
            dict.fromkeys(
                structure["structure_type"]
                for structure in structures
                if structure.get("structure_type")
            )
        )

        # Recognize controls only when they begin a line in the chunk.
        # This avoids treating ordinary prose references as controls.
        control_identifiers = list(
            dict.fromkeys(
                match.upper()
                for match in re.findall(
                    r"(?im)^[ \t]*(CC\d+(?:\.\d+)+)\b",
                    text or "",
                )
            )
        )

        # Article identity comes from inferred section context, not
        # from arbitrary mentions of "Article 16" in body text.
        article_identifiers = list(
            dict.fromkeys(
                match.group(1)
                for path_item in section_path
                if (
                    match := re.match(
                        r"^\s*Article\s+(\d+[A-Za-z]?)\b",
                        path_item,
                        re.IGNORECASE,
                    )
                )
            )
        )

        if control_identifiers:
            # A chunk containing several controls must not be assigned
            # one arbitrary control identifier.
            identifiers = control_identifiers
            inferred_type = "control"
        elif inferred_identifiers:
            identifiers = inferred_identifiers
            inferred_type = None
        elif article_identifiers:
            identifiers = article_identifiers
            inferred_type = "article"
        else:
            identifiers = []
            inferred_type = None

        identifier = (
            identifiers[0]
            if len(identifiers) == 1
            else None
        )

        parent_identifier = (
            parent_identifiers[0]
            if len(parent_identifiers) == 1
            else None
        )

        if inferred_type:
            structure_type = inferred_type
        else:
            structure_type = (
                structure_types[0]
                if len(structure_types) == 1
                else None
            )

        return {
            "identifier": identifier,
            "parent_identifier": parent_identifier,
            "structure_type": structure_type,
            "structural_identifiers": identifiers,
        }

    @staticmethod
    def _resolve_section_path(
        elements: list[DocumentElement],
    ) -> list[str]:
        for element in elements:
            if element.section_path:
                return list(element.section_path)

        return []
