import sys
from collections import Counter
from pathlib import Path

from services.ingestion.domain.serialization import document_from_dict

from services.ingestion.parsers.docling_parser import DoclingParser
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
)
from services.ingestion.chunking.chunker import ComplianceChunker

from tests.fixtures.docling_cache import load_cached_document
from tests.test_cached_ingestion_pipeline import build_artifact, build_canonical_document, restore_candidates

# Reuse these helpers from your existing working test:
# build_canonical_document
# build_artifact
# restore_candidates


def inspect_canonical(label, document):
    """Report structural information on a canonical document."""
    identifiers = []
    structure_types = Counter()
    sources = Counter()
    source_refs = set()

    for element in document.elements:
        metadata = element.metadata or {}
        structure = metadata.get("structure") or {}

        source_ref = metadata.get("source_ref")

        if source_ref:
            source_refs.add(source_ref)

        if structure.get("identifier"):
            identifiers.append(
                (source_ref, structure["identifier"])
            )

        if structure.get("structure_type"):
            structure_types[structure["structure_type"]] += 1

        if structure.get("source"):
            sources[structure["source"]] += 1

    print(f"\n[{label}]")
    print(f"Canonical elements: {len(document.elements)}")
    print(f"Unique source refs: {len(source_refs)}")
    print(f"Elements with identifiers: {len(identifiers)}")
    print(f"Structure types: {dict(structure_types)}")
    print(f"Structure sources: {dict(sources)}")

    for source_ref, identifier in identifiers[:10]:
        print(f"  identifier={identifier!r}, source_ref={source_ref!r}")

    return identifiers


def inspect_chunks(chunks):
    """Report structural metadata transferred to chunks."""
    counts = Counter()

    for chunk in chunks:
        counts["total"] += 1

        if chunk.identifier:
            counts["with_identifier"] += 1

        if chunk.parent_identifier:
            counts["with_parent_identifier"] += 1

        if chunk.structure_type:
            counts["with_structure_type"] += 1

        if chunk.section_path:
            counts["with_section_path"] += 1

        metadata = chunk.metadata or {}

        if metadata.get("structural_identifiers"):
            counts["with_structural_identifiers"] += 1

        if metadata.get("unmatched_source_refs"):
            counts["with_unmatched_source_refs"] += 1

    print("\n[STAGE 3] AFTER COMPLIANCE CHUNKING")
    print(f"Chunk summary: {dict(counts)}")

    for chunk in chunks[:10]:
        metadata = chunk.metadata or {}

        print({
            "chunk_index": chunk.chunk_index,
            "identifier": chunk.identifier,
            "parent_identifier": chunk.parent_identifier,
            "structure_type": chunk.structure_type,
            "section_path": chunk.section_path,
            "element_indexes": chunk.element_indexes,
            "structural_identifiers": metadata.get(
                "structural_identifiers"
            ),
            "unmatched_source_refs": metadata.get(
                "unmatched_source_refs"
            ),
        })


def run(path):
    print("\n" + "=" * 80)
    print(f"STRUCTURE HANDOFF: {path}")
    print("=" * 80)

    # Stage 0: Load the actual cached Docling document.
    parser = DoclingParser()
    docling_document = load_cached_document(path)

    inspect_docling_structure(docling_document)
    # Stage 1: Normalize and build candidates using the real parser.
    parser._normalize_docling_document(docling_document)
    candidates = parser._build_chunk_candidates(docling_document)

    print("\n[STAGE 1A] PARSER OUTPUT")
    print(f"Chunk candidates: {len(candidates)}")

    candidate_refs = {
        ref
        for candidate in candidates
        for ref in candidate.source_refs
    }

    print(f"Unique candidate source refs: {len(candidate_refs)}")

    for candidate in candidates[:5]:
        print({
            "source_refs": candidate.source_refs,
            "page_start": candidate.page_start,
            "page_end": candidate.page_end,
            "headings": candidate.headings,
            "text_preview": candidate.text[:160],
        })

    # Use the same canonical-document and artifact-building path
    # as the existing working test.
    canonical = build_canonical_document(
        parser, docling_document, path
    )

    print("\n[STAGE 1D] CANONICAL ELEMENT METADATA")

    for index, element in enumerate(canonical.elements):
        metadata = element.metadata or {}
        text = element.text or ""

        if (
            index < 10
            or "Article 6" in text
            or "Article 16" in text
            or "CC6.1.4" in text
            or "SECTION 1" in text
        ):
            print({
                "index": index,
                "text": text[:180],
                "element_type": str(element.element_type),
                "metadata": metadata,
            })

    artifact = build_artifact(canonical, candidates)

    # Restore through the production serialization boundary.
    restored_document = document_from_dict(artifact)
    restored_candidates = restore_candidates(artifact)

    print("\n[STAGE 1B] AFTER SERIALIZATION/RESTORATION")
    print(f"Restored candidates: {len(restored_candidates)}")

    original_identifiers = inspect_canonical(
        "STAGE 1C: CANONICAL DOCUMENT BEFORE INFERENCE",
        restored_document,
    )

    # Stage 2: Run structure inference.
    structured_document = StructureInferenceService().infer(
        restored_document
    )

    inferred_identifiers = inspect_canonical(
        "STAGE 2: AFTER STRUCTURE INFERENCE",
        structured_document,
    )

    original_set = set(original_identifiers)
    inferred_set = set(inferred_identifiers)

    lost = original_set - inferred_set
    added = inferred_set - original_set

    print("\n[STAGE 2] IDENTIFIER COMPARISON")
    print(f"Identifiers before inference: {len(original_set)}")
    print(f"Identifiers after inference:  {len(inferred_set)}")
    print(f"Existing identifiers lost:   {len(lost)}")
    print(f"New identifiers added:       {len(added)}")

    for item in list(lost)[:10]:
        print(f"  LOST: {item}")

    for item in list(added)[:10]:
        print(f"  ADDED: {item}")

    # Stage 3: Run the actual chunker in memory.
    chunks = ComplianceChunker().chunk(
        structured_document,
        restored_candidates,
    )

    inspect_chunks(chunks)

    print(f"\nCompleted: {path}")


def inspect_docling_structure(docling_document):
    print("\n[STAGE 0] ORIGINAL DOCLING STRUCTURE")

    texts = getattr(docling_document, "texts", []) or []
    tables = getattr(docling_document, "tables", []) or []

    print(f"Docling text items: {len(texts)}")
    print(f"Docling tables: {len(tables)}")

    counts = Counter()
    examples = []

    for collection_name, collection in (
        ("texts", texts),
        ("tables", tables),
    ):
        for index, item in enumerate(collection):
            data = item.model_dump(
                mode="json",
                exclude_none=True,
            )

            counts["items"] += 1

            if data.get("label"):
                counts[f"label:{data['label']}"] += 1

            if data.get("self_ref"):
                counts["with_self_ref"] += 1

            if data.get("parent"):
                counts["with_parent"] += 1

            if data.get("children"):
                counts["with_children"] += 1

            # Capture likely structural identifiers or references.
            interesting = {
                key: value
                for key, value in data.items()
                if key in {
                    "self_ref",
                    "parent",
                    "children",
                    "label",
                    "text",
                    "orig",
                    "prov",
                    "enumerated",
                    "marker",
                }
            }

            text = str(data.get("text", ""))

            if (
                any(
                    token in text
                    for token in (
                        "CC6.1.4",
                        "CC6.1.5",
                        "CC6.1.6",
                        "Article 6",
                        "Article 16",
                    )
                )
                or data.get("label") in {
                    "section_header",
                    "title",
                }
            ):
                examples.append(
                    (collection_name, index, interesting)
                )

    print(f"Metadata summary: {dict(counts)}")

    for collection_name, index, item in examples[:20]:
        print({
            "collection": collection_name,
            "index": index,
            "data": item,
        })


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python -u "
            "tests/scripts/test_cached_structure_handoff.py "
            "<cached-docling.json> [another-cached-docling.json ...]"
        )
        return 2

    for argument in sys.argv[1:]:
        path = Path(argument)

        if not path.exists():
            print(f"ERROR: Cache file not found: {path}")
            return 1

        run(str(path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
