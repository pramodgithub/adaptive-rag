from abc import ABC, abstractmethod
from dataclasses import dataclass

from services.ingestion.domain.document import CanonicalDocument


@dataclass
class ChunkData:
    text: str
    chunk_index: int
    page_number: int


class DocumentParser(ABC):

    @abstractmethod
    def parse(self, file_path: str) -> CanonicalDocument:
        raise NotImplementedError
