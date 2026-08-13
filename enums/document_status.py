from enum import Enum


class DocumentStatus(str, Enum):
    ACTIVE = "ACTIVE"       # normal, usable
    ARCHIVED = "ARCHIVED"   # user-archived, hidden from default views, not deleted
    DELETED = "DELETED"     # soft-deleted — if you want an undo window before hard delete
