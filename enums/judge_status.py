from enum import Enum


class JudgeStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
