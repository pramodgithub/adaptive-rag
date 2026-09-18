from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ElementType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    IMAGE = "image"
    FOOTNOTE = "footnote"
    UNKNOWN = "unknown"


@dataclass
class TableData:
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class DocumentElement:
    element_type: ElementType
    text: str
    page_start: int | None = None
    page_end: int | None = None
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    table: TableData | None = None
