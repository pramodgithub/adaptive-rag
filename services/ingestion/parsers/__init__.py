"""Document parser implementations for ingestion."""

from .base import DocumentParser
from .factory import ParserFactory

__all__ = ["DocumentParser", "ParserFactory"]
