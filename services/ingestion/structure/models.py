from dataclasses import dataclass, field


@dataclass
class InferredStructure:
    section_path: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "generic"
    structure_type: str | None = None
    identifier: str | None = None
    parent_identifier: str | None = None
