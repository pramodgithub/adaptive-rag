from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ParsedPage:
    page_number: int
    text: str


@dataclass
class ParsedDocument:
    text: str
    pages: list[ParsedPage]
    page_count: int | None = None


@dataclass
class ChunkData:

    text: str
    chunk_index: int
    page_number: int


class DocumentParser(ABC):

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        pass
