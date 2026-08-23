from .base import DocumentParser, ParsedDocument


class TextParser(DocumentParser):

    def parse(self, file_path: str) -> ParsedDocument:

        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()

        return ParsedDocument(
            text=text
        )
