from .base import DocumentParser
from .docling_parser import DoclingParser
from .text import TextParser


class ParserFactory:

    _parsers = {
        "application/pdf": DoclingParser,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DoclingParser,
        "text/html": DoclingParser,
        "text/plain": TextParser,
    }

    @classmethod
    def get_parser(cls, mime_type: str) -> DocumentParser:
        parser_class = cls._parsers.get(mime_type)

        if not parser_class:
            raise ValueError(
                f"Unsupported document type: {mime_type}"
            )

        return parser_class()
