import re
from pathlib import Path

from docling_core.types.doc import DocItemLabel, DoclingDocument

from services.ingestion.parsers.parsed_document import ParsedDocument

from .base import DocumentParser
from .docling_parser import DoclingParser


class TextParser(DocumentParser):
    """Plain .txt files, through the same steps as PDF and Word files.

    The text is split into paragraphs and put into a Docling document,
    then handed to DoclingParser.parse_document. So a .txt gets the same
    heading detection ("Article 7", "Section 2", "1.2 Scope"), levels,
    cleanup and chunking as every other format.
    """

    def __init__(self):
        self.docling_parser = DoclingParser()

    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        source = Path(file_path)
        raw = source.read_bytes()

        # utf-8-sig drops a byte-order mark if there is one.
        text = raw.decode("utf-8-sig", errors="replace")

        document = DoclingDocument(name=source.stem)

        for paragraph in self._paragraphs(text):
            document.add_text(label=DocItemLabel.TEXT, text=paragraph)

        return self.docling_parser.parse_document(
            document=document,
            source_name=source.name,
        )

    @staticmethod
    def _paragraphs(text: str) -> list[str]:
        """Blank lines separate paragraphs. A short first line that looks
        like a heading ("Article 7", "2.1 Scope") becomes its own item, so
        the parser can turn it into a heading."""
        heading = DoclingParser._HEADING_PATTERN
        max_heading = DoclingParser._HEADING_MAX_CHARS
        paragraphs: list[str] = []

        for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
            lines = [line.strip()
                     for line in block.split("\n") if line.strip()]

            if not lines:
                continue

            first = lines[0]
            if (
                len(lines) > 1
                and len(first) <= max_heading
                and not first.endswith((".", ";", ","))
                and heading.match(first)
            ):
                second = lines[1]

                # "Article 1" with its title on the next line becomes one
                # heading line: "Article 1: Subject-matter and objectives".
                if (
                    DoclingParser._is_number_only(first)
                    and len(second) <= max_heading
                    and not second.endswith((".", ";", ","))
                ):
                    paragraphs.append(f"{first.rstrip('.:')}: {second}")
                    lines = lines[2:]
                else:
                    paragraphs.append(first)
                    lines = lines[1:]

            # Lines wrapped inside a paragraph are joined back together.
            if lines:
                paragraphs.append(" ".join(lines))

        return paragraphs
