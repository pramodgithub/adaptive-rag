from pathlib import Path

from services.ingestion.chunking.chunker import ComplianceChunker
from services.ingestion.domain.serialization import (
    document_from_dict,
)
from services.ingestion.parsers.chunk_candidate import ChunkCandidate
from services.ingestion.parsers.docling_parser import DoclingParser
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
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
):
    elements = []

    for item, level in document.iterate_items():
        element = parser._convert_item(
            item=item,
            level=level,
        )

        if element is not None:
            elements.append(element)

    return parser_canonical_document(
        parser,
        document,
        path,
        elements,
    )


def parser_canonical_document(
    parser: DoclingParser,
    document,
    path: str,
    elements,
):
    from services.ingestion.domain.document import (
        CanonicalDocument,
    )

    return CanonicalDocument(
        title=Path(path).name,
        elements=elements,
        page_count=parser._get_page_count(document),
        metadata={
            "source_format": "cached-docling",
            "parser": "docling",
        },
    )


def build_artifact(
    document,
    candidates,
):
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


def restore_candidates(
    parsed: dict,
) -> list[ChunkCandidate]:
    return [
        ChunkCandidate(
            text=item["text"],
            source_refs=item.get("source_refs", []),
            page_start=item.get("page_start"),
            page_end=item.get("page_end"),
            headings=item.get("headings", []),
        )
        for item in parsed.get(
            "chunk_candidates",
            [],
        )
    ]


def run(path: str):
    print("=" * 80)
    print(path)
    print("=" * 80)

    parser = DoclingParser()

    docling_document = load_cached_document(path)

    parser._normalize_docling_document(
        docling_document
    )

    candidates = parser._build_chunk_candidates(
        docling_document
    )

    canonical = build_canonical_document(
        parser,
        docling_document,
        path,
    )

    # This mirrors parse_document's artifact.
    artifact = build_artifact(
        canonical,
        candidates,
    )

    # This mirrors chunk_document.
    restored_document = document_from_dict(
        artifact
    )

    restored_candidates = restore_candidates(
        artifact
    )

    structure_inference = StructureInferenceService()

    structured_document = structure_inference.infer(
        restored_document
    )

    chunks = ComplianceChunker().chunk(
        structured_document,
        restored_candidates,
    )

    print(
        f"Canonical elements: "
        f"{len(restored_document.elements)}"
    )

    print(
        f"Candidates: "
        f"{len(restored_candidates)}"
    )

    print(
        f"Chunks: "
        f"{len(chunks)}"
    )

    assert restored_candidates

    assert len(chunks) == len(
        restored_candidates
    )

    assert all(
        chunk.text.strip()
        for chunk in chunks
    )

    assert all(
        len(chunk.text) <= 3200
        for chunk in chunks
    )

    # Verify provenance survived the artifact round-trip.
    source_refs = [
        element.metadata.get("source_ref")
        for element in restored_document.elements
    ]

    assert any(source_refs)

    print("PASS")


if __name__ == "__main__":
    for test_file in TEST_FILES:
        run(test_file)
