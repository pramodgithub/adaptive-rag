from datetime import date
from enum import Enum

from pydantic import BaseModel

from enums.authority_levels import VerificationStatus


class AuthorityLevel(str, Enum):
    PRIMARY = "primary"
    OFFICIAL_GUIDANCE = "official_guidance"
    CERTIFIED_STANDARD = "certified_standard"
    ORGANIZATIONAL_POLICY = "organizational_policy"
    SECONDARY = "secondary"
    UNVERIFIED = "unverified"


class EvidenceMetadata(BaseModel):
    source_type: str
    issuer: str | None = None
    jurisdiction: str | None = None
    authority_level: AuthorityLevel
    publication_date: date | None = None
    effective_date: date | None = None
    expiration_date: date | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
