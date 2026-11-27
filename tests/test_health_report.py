"""Health report on cached documents: what an upload would be judged as.

Run from /app inside the worker:
    python -m tests.test_health_report
    python -m tests.test_health_report tests/data/cache/<new>.docling.json
"""
import json
import sys

from services.ingestion.chunking.chunker import ComplianceChunker
from services.ingestion.chunking.health import build_health_report
from services.ingestion.domain.serialization import (
    document_from_dict,
    document_to_dict,
)
from services.ingestion.parsers.docling_parser import DoclingParser
from services.ingestion.structure.structure_inference import (
    StructureInferenceService,
)
from tests.fixtures.docling_cache import load_cached_document

DEFAULT_PATHS = [
    "tests/data/cache/gdpr.docling.json",
    "tests/data/cache/SOC2.docling.json",
]


def main():
    parser = DoclingParser()
    service = StructureInferenceService()
    chunker = ComplianceChunker()

    for path in sys.argv[1:] or DEFAULT_PATHS:
        name = path.rsplit("/", 1)[-1]
        parsed = parser.parse_document(load_cached_document(path), name)
        reloaded = document_from_dict(
            json.loads(json.dumps(document_to_dict(
                parsed.canonical), ensure_ascii=False))
        )
        structured = service.infer(reloaded)
        chunks = chunker.chunk(structured, parsed.chunk_candidates)
        report = build_health_report(
            structured, parsed.chunk_candidates, chunks)

        print(
            f"\n=== {name}: {report['status'].upper()} ({report['summary']}) ===")
        for check in report["checks"]:
            mark = "OK" if check["passed"] else check["level"].upper()
            print(f"  [{mark:6}] {check['name']}")
        m = report["metrics"]
        print(f"  coverage {m['content_coverage']}, chunks {m['chunks']}, "
              f"with path {m['chunks_with_path']}, with id {m['chunks_with_id']}, "
              f"levels {m['heading_levels']}")
        if report["unknown_id_shapes"]:
            print(f"  unknown ID shapes: {report['unknown_id_shapes']}")
        for text in report["missing_examples"]:
            print(f"  missing e.g. {text!r}")


if __name__ == "__main__":
    main()
