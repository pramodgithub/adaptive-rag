from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SemanticEntityType(str, Enum):
    CONTROL = "control"
    CONTROL_ENHANCEMENT = "control_enhancement"
    ARTICLE = "article"
    RECITAL = "recital"
    REQUIREMENT = "requirement"
    SECTION = "section"
    OTHER = "other"


class SemanticValidationStatus(str, Enum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    REJECTED = "rejected"


@dataclass
class SemanticEntity:
    framework: str
    identifier: str
    entity_type: SemanticEntityType

    title: str | None = None
    parent_identifier: str | None = None

    confidence: float = 0.0
    validation_status: SemanticValidationStatus = (
        SemanticValidationStatus.REVIEW
    )

    source: str = "llm"
    metadata: dict[str, Any] = field(default_factory=dict)
