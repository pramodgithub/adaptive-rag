from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import DocumentElement

from .models import DocumentChunk
from .splitter import ChunkSizeSplitter


class ComplianceChunker:
    BOUNDARY_TYPES = {
        "control",
        "control_enhancement",
        "article",
        "recital",
    }

    def __init__(
        self,
        splitter: ChunkSizeSplitter | None = None,
    ):
        self.splitter = splitter or ChunkSizeSplitter()

    def chunk(
        self,
        document: CanonicalDocument,
    ) -> list[DocumentChunk]:
        semantic_chunks = self._build_semantic_chunks(document)

        chunks: list[DocumentChunk] = []

        for semantic_chunk in semantic_chunks:
            chunks.extend(
                self.splitter.split(semantic_chunk)
            )

        for index, chunk in enumerate(chunks):
            chunk.chunk_index = index

        return chunks

    def _build_semantic_chunks(
        self,
        document: CanonicalDocument,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        current_elements: list[tuple[int, DocumentElement]] = []

        for index, element in enumerate(document.elements):
            if self._is_boundary(element) and current_elements:
                chunks.append(
                    self._build_chunk(
                        chunk_index=len(chunks),
                        elements=current_elements,
                    )
                )
                current_elements = []

            if element.text.strip():
                current_elements.append(
                    (index, element)
                )

        if current_elements:
            chunks.append(
                self._build_chunk(
                    chunk_index=len(chunks),
                    elements=current_elements,
                )
            )

        return chunks

    def _is_boundary(
        self,
        element: DocumentElement,
    ) -> bool:
        structure = element.metadata.get("structure", {})

        return (
            structure.get("structure_type")
            in self.BOUNDARY_TYPES
        )

    def _build_chunk(
        self,
        chunk_index: int,
        elements: list[tuple[int, DocumentElement]],
    ) -> DocumentChunk:
        indexes = [index for index, _ in elements]
        source_elements = [element for _, element in elements]

        first = source_elements[0]
        structure = first.metadata.get("structure", {})

        text = "\n\n".join(
            element.text
            for element in source_elements
            if element.text.strip()
        )

        return DocumentChunk(
            chunk_index=chunk_index,
            text=text,
            page_start=min(
                (
                    element.page_start
                    for element in source_elements
                    if element.page_start is not None
                ),
                default=None,
            ),
            page_end=max(
                (
                    element.page_end
                    for element in source_elements
                    if element.page_end is not None
                ),
                default=None,
            ),
            section_path=list(first.section_path),
            structure_type=structure.get("structure_type"),
            identifier=structure.get("identifier"),
            parent_identifier=structure.get("parent_identifier"),
            element_indexes=indexes,
            metadata={
                "source": "canonical_document",
            },
        )
