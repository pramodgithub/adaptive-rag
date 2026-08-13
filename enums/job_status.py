from enum import Enum


class JobStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    EMBEDDING = "EMBEDDING"
    GRAPH_BUILD = "GRAPH_BUILD"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
