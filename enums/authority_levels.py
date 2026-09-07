from enum import Enum


class AuthorityLevel(str, Enum):
    PRIMARY = "primary"
    OFFICIAL_GUIDANCE = "official_guidance"
    CERTIFIED_STANDARD = "certified_standard"
    ORGANIZATIONAL_POLICY = "organizational_policy"
    SECONDARY = "secondary"
    UNVERIFIED = "unverified"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
