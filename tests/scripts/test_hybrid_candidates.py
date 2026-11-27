from pathlib import Path

from services.ingestion.chunking.chunker import ComplianceChunker
from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.parsers.chunk_candidate import ChunkCandidate
from services.ingestion.parsers.docling_parser import DoclingParser
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
)
from services.ingestion.domain.serialization import (
    document_from_dict,
)
from tests.fixtures.docling_cache import load_cached_document


TEST_FILES = [
    "tests/data/SOC2.docling.json",
    "tests/data/CELEX_32016R0679_EN_TXT.docling.json",
]


def build_canonical_document(
    parser: DoclingParser,
    document,
    path: str,
) -> CanonicalDocument:
    elements = []

    for item, level in document.iterate_items():
        element = parser._convert_item(
            item=item,
            level=level,
        )

        if element is not None:
            elements.append(element)

    return CanonicalDocument(
        title=Path(path).name,
        elements=elements,
        page_count=parser._get_page_count(document),
        metadata={
            "parser": "docling",
        },
    )


def build_candidates(
    parser: DoclingParser,
    document,
) -> list[ChunkCandidate]:
    parser._normalize_docling_document(document)

    return parser._build_chunk_candidates(document)


def serialize_artifact(
    document: CanonicalDocument,
    candidates: list[ChunkCandidate],
) -> dict:
    return {
        "title": document.title,
        "page_count": document.page_count,
        "metadata": document.metadata,
        "elements": [
            {
                "element_type": element.element_type.value,
                "text": element.text,
                "page_start": element.page_start,
                "page_end": element.page_end,
                "section_path": element.section_path,
                "metadata": element.metadata,
                "table": (
                    {
                        "headers": element.table.headers,
                        "rows": element.table.rows,
                    }
                    if element.table
                    else None
                ),
            }
            for element in document.elements
        ],
        "chunk_candidates": [
            {
                "text": candidate.text,
                "source_refs": candidate.source_refs,
                "page_start": candidate.page_start,
                "page_end": candidate.page_end,
                "headings": candidate.headings,
            }
            for candidate in candidates
        ],
    }


def run(path: str) -> None:
    print("=" * 80)
    print(path)
    print("=" * 80)

    parser = DoclingParser()

    document = load_cached_document(path)

    candidates = build_candidates(
        parser,
        document,
    )

    canonical = build_canonical_document(
        parser,
        document,
        path,
    )

    structure_inference = StructureInferenceService()

    structured_document = structure_inference.infer(
        canonical
    )

    artifact = serialize_artifact(
        structured_document,
        candidates,
    )

    print(
        f"Original elements: {len(structured_document.elements)}"
    )
    print(
        f"Original candidates: {len(candidates)}"
    )

    # Validate serialization boundary.
    assert len(artifact["elements"]) == len(
        structured_document.elements
    )

    assert len(artifact["chunk_candidates"]) == len(
        candidates
    )

    restored_document = document_from_dict(
        artifact
    )
    restored_candidates = [
        ChunkCandidate(
            text=item["text"],
            source_refs=item.get("source_refs", []),
            page_start=item.get("page_start"),
            page_end=item.get("page_end"),
            headings=item.get("headings", []),
        )
        for item in artifact["chunk_candidates"]
    ]

    # Validate candidate round-trip.
    assert len(restored_candidates) == len(candidates)

    assert (
        restored_candidates[0].text
        == candidates[0].text
    )

    assert (
        restored_candidates[0].source_refs
        == candidates[0].source_refs
    )

    # Validate actual chunking path.
    chunker = ComplianceChunker()

    chunks = chunker.chunk(
        restored_document,
        restored_candidates,
    )

    print(
        f"Generated chunks: {len(chunks)}"
    )

    assert chunks

    assert len(chunks) == len(restored_candidates)

    assert all(
        chunk.text.strip()
        for chunk in chunks
    )

    assert all(
        len(chunk.text) <= 3200
        for chunk in chunks
    )

    print("PASS")


if __name__ == "__main__":
    for test_file in TEST_FILES:
        run(test_file)
