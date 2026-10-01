from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import DocumentElement
from services.ingestion.parsers.chunk_candidate import ChunkCandidate

from .models import DocumentChunk
from .splitter import ChunkSizeSplitter


from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import DocumentElement
from services.ingestion.parsers.chunk_candidate import ChunkCandidate

from .models import DocumentChunk
from .splitter import ChunkSizeSplitter


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
            element.metadata.get("source_ref"): index
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
            final_chunks.extend(
                self.splitter.split(chunk)
            )

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
        element_indexes = [
            ref_to_index[ref]
            for ref in candidate.source_refs
            if ref in ref_to_index
        ]

        source_elements = [
            document.elements[index]
            for index in element_indexes
        ]

        structure = self._resolve_structure(
            source_elements
        )

        return DocumentChunk(
            chunk_index=chunk_index,
            text=candidate.text,
            page_start=candidate.page_start,
            page_end=candidate.page_end,
            section_path=self._resolve_section_path(
                source_elements
            ),
            structure_type=structure.get("structure_type"),
            identifier=structure.get("identifier"),
            parent_identifier=structure.get(
                "parent_identifier"
            ),
            element_indexes=element_indexes,
            metadata={
                "source": "hybrid_chunker",
                "headings": candidate.headings,
            },
        )

    @staticmethod
    def _resolve_structure(
        elements: list[DocumentElement],
    ) -> dict:
        for element in elements:
            structure = element.metadata.get("structure")

            if structure:
                return structure

        return {}

    @staticmethod
    def _resolve_section_path(
        elements: list[DocumentElement],
    ) -> list[str]:
        for element in elements:
            if element.section_path:
                return list(element.section_path)

        return []
