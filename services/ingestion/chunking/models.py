from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentChunk:
    chunk_index: int
    text: str

    page_start: int | None = None
    page_end: int | None = None

    section_path: list[str] = field(default_factory=list)

    structure_type: str | None = None
    identifier: str | None = None
    parent_identifier: str | None = None

    element_indexes: list[int] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
