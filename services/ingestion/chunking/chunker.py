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

        chunks = [
            self._build_chunk(
                document=document,
                candidate=candidate,
                chunk_index=index,
                ref_to_index=ref_to_index,
            )
            for index, candidate in enumerate(candidates)
        ]

        final_chunks: list[DocumentChunk] = []

        for chunk in chunks:
            final_chunks.extend(self.splitter.split(chunk))

        for index, chunk in enumerate(final_chunks):
            chunk.chunk_index = index

        return final_chunks

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
