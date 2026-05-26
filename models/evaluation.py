from dataclasses import dataclass
from typing import Optional


@dataclass
class Evaluation:
    query: str
    score: float
    notes: Optional[str] = None
