from pypdf import PdfReader

from .base import (
    DocumentParser,
    ParsedDocument,
    ParsedPage
)


class PDFParser(DocumentParser):

    def parse(self, file_path: str) -> ParsedDocument:

        reader = PdfReader(file_path)

        pages = []

        for index, page in enumerate(reader.pages):

            text = page.extract_text() or ""

            pages.append(
                ParsedPage(
                    page_number=index + 1,
                    text=text
                )
            )

        return ParsedDocument(
            text="\n\n".join(
                page.text
                for page in pages
            ),
            pages=pages,
            page_count=len(pages)
        )
