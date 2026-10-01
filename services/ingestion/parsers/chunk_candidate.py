from dataclasses import dataclass, field


@dataclass
class ChunkCandidate:
    text: str
    source_refs: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    headings: list[str] = field(default_factory=list)
