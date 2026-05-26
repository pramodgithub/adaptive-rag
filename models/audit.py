from dataclasses import dataclass
from datetime import datetime


@dataclass
class AuditRecord:
    event: str
    timestamp: datetime
    details: dict
