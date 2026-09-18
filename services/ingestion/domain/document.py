from dataclasses import dataclass, field
from typing import Any

from .elements import DocumentElement


@dataclass
class CanonicalDocument:
    title: str
    elements: list[DocumentElement] = field(default_factory=list)
    page_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(
            element.text
            for element in self.elements
            if element.text.strip()
        )
