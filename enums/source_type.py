from enum import Enum


class EvidenceSourceType(str, Enum):
    REGULATION = "regulation"
    OFFICIAL_GUIDANCE = "official_guidance"
    CERTIFIED_STANDARD = "certified_standard"
    ORGANIZATIONAL_POLICY = "organizational_policy"
    INTERNAL_PROCEDURE = "internal_procedure"
    AUDIT_REPORT = "audit_report"
    CONTRACT = "contract"
    TECHNICAL_DOCUMENTATION = "technical_documentation"
    SECONDARY = "secondary"
    OTHER = "other"
