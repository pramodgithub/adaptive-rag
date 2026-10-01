from dataclasses import dataclass

from docling_core.types.doc import DoclingDocument

from services.ingestion.domain.document import CanonicalDocument
from .chunk_candidate import ChunkCandidate


@dataclass
class ParsedDocument:
    canonical: CanonicalDocument
    docling_document: DoclingDocument
    chunk_candidates: list[ChunkCandidate]
