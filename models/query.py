from dataclasses import dataclass
from typing import Optional


@dataclass
class Query:
    text: str
    top_k: int = 5
    filters: Optional[dict] = None
