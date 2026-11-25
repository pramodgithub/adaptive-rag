from services.ingestion.chunking.models import DocumentChunk
from services.ingestion.semantics.extractor import (
    SemanticEntityExtractor,
)
from services.ingestion.semantics.models import (
    SemanticEntityType,
    SemanticValidationStatus,
)


def test_extracts_multiple_entities_from_chunk():
    chunk = DocumentChunk(
        chunk_index=0,
        text=(
            "CC6.1.4 Access reviews are performed.\n"
            "CC6.1.5 Access is reviewed periodically.\n"
            "CC6.1.6 Access exceptions are documented."
        ),
        section_path=["Logical Access"],
    )

    entities = SemanticEntityExtractor().extract(
        chunk,
        framework="soc2",
    )

    assert [entity.identifier for entity in entities] == [
        "CC6.1.4",
        "CC6.1.5",
        "CC6.1.6",
    ]

    assert entities[0].title == "Access reviews are performed"
    assert entities[0].parent_identifier == "CC6.1"
    assert entities[0].entity_type == SemanticEntityType.OTHER
    assert entities[0].validation_status == SemanticValidationStatus.REVIEW
    assert entities[0].source == "deterministic"


def test_extracts_explicitly_labelled_articles():
    chunk = DocumentChunk(
        chunk_index=1,
        text="Article 5 Protection of personal data.",
    )

    entities = SemanticEntityExtractor().extract(chunk)

    assert len(entities) == 1
    assert entities[0].identifier == "5"
    assert entities[0].entity_type == SemanticEntityType.ARTICLE
    assert entities[0].framework == "unknown"


def test_returns_no_entities_without_recognizable_identifiers():
    chunk = DocumentChunk(
        chunk_index=2,
        text="Access reviews should be performed periodically.",
    )

    assert SemanticEntityExtractor().extract(chunk) == []


if __name__ == "__main__":
    test_functions = [
        obj for name, obj in list(globals().items())
        if name.startswith("test_") and callable(obj)
    ]

    print(f"Running {len(test_functions)} test(s)...\n" + "=" * 40)
    for test_func in test_functions:
        test_func()
        print(f"  ✓ {test_func.__name__}")
    print("=" * 40 + "\nPASS: All semantic extractor tests passed!")
