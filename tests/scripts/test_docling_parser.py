import os

import pypdfium2 as pdfium

from services.ingestion.parsers.docling_parser import DoclingParser


FILE_PATH = os.getenv(
    "TEST_DOCUMENT",
    "tests/data/NIST.SP.800-53r5.pdf",
)

PAGES_PER_CHUNK = int(os.getenv("PAGES_PER_CHUNK", "50"))
ELEMENTS_PREVIEW_PER_CHUNK = 20


def get_total_pages(file_path: str) -> int:
    pdf = pdfium.PdfDocument(file_path)
    total = len(pdf)
    pdf.close()
    return total


def print_elements(elements, limit):
    for index, element in enumerate(elements[:limit], start=1):
        print(f"[{index}] {element.element_type.value}")
        print(f"Page: {element.page_start}")
        print(f"Text: {element.text[:300]}")
        print(f"Metadata: {element.metadata}")
        print()


def main():
    parser = DoclingParser()
    total_pages = get_total_pages(FILE_PATH)

    title = None
    all_elements = []

    for start in range(1, total_pages + 1, PAGES_PER_CHUNK):
        end = min(start + PAGES_PER_CHUNK - 1, total_pages)

        print(f"Parsing pages {start}-{end} of {total_pages}...")

        # page_range is 1-indexed, inclusive, and passed straight through to
        # docling's DocumentConverter.convert() - no file splitting needed,
        # so element.page_start already reflects the ORIGINAL document.
        chunk_document = parser.parse(FILE_PATH, page_range=(start, end))

        if title is None:
            title = chunk_document.title

        all_elements.extend(chunk_document.elements)

        print(
            f"\n--- First {ELEMENTS_PREVIEW_PER_CHUNK} Elements (pages {start}-{end}) ---\n")
        print_elements(chunk_document.elements, ELEMENTS_PREVIEW_PER_CHUNK)

    print(f"\nFile: {FILE_PATH}")
    print(f"Title: {title}")
    print(f"Pages: {total_pages}")
    print(f"Elements: {len(all_elements)}")

    counts = {}

    for element in all_elements:
        key = element.element_type.value
        counts[key] = counts.get(key, 0) + 1

    print("\n--- Element Counts ---")

    for element_type, count in sorted(counts.items()):
        print(f"{element_type}: {count}")


if __name__ == "__main__":
    main()
