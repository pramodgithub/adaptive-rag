"""Stage 2 check: StructureInferenceService on a cached Docling document.

Runs the real code in pipeline order:
    DoclingParser.parse_document -> JSON save/reload (as parse_task/chunk_task)
    -> StructureInferenceService.infer
Short output: one line per check, a few examples where something needs a look.

Run from /app inside the worker:
    python -m tests.test_stage2_structure
    python -m tests.test_stage2_structure tests/data/cache/SOC2.docling.json
"""
import json
import sys
from collections import Counter

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


def line(status, name, detail=""):
    print(f"  [{status:5}] {name:30} {detail}")


def examples(items, n=2):
    for text in items[:n]:
        print(f"           e.g. {str(text)[:110]}")


def short(path):
    return " > ".join(p[:28] for p in path) or "(empty)"


def kind(element):
    return element.element_type.name.lower()


def expected_paths(elements):
    """The path each element should get from heading levels alone."""
    stack: list[tuple[int, str]] = []
    expected = []
    for e in elements:
        if kind(e) == "title":
            stack = []
            expected.append([])
            continue
        level = e.metadata.get("heading_level")
        if kind(e) == "heading" and level:
            stack = [(lvl, txt) for lvl, txt in stack if lvl < level]
            stack.append((level, e.text))
        expected.append([txt for _, txt in stack])
    return expected


def run(path, parser, service):
    name = path.rsplit("/", 1)[-1]
    print(f"\n=== {name} ===")
    parsed = parser.parse_document(load_cached_document(path), name)

    # Same save and reload as parse_task -> chunk_task.
    reloaded = document_from_dict(
        json.loads(json.dumps(document_to_dict(
            parsed.canonical), ensure_ascii=False))
    )
    headings = [e for e in reloaded.elements if kind(e) == "heading"]
    kept = sum(1 for h in headings if h.metadata.get("heading_level"))
    line("OK" if kept == len(headings) else "CHECK", "heading level after reload",
         f"{kept} of {len(headings)}")

    structured = service.infer(reloaded)
    elements = structured.elements
    expected = expected_paths(elements)

    # 1. Heading paths.
    bad_h = [(e, exp) for e, exp in zip(elements, expected)
             if kind(e) == "heading" and e.section_path != exp]
    line("OK" if not bad_h else "CHECK", "heading paths match levels",
         f"{len(headings) - len(bad_h)} of {len(headings)}")
    examples(
        [f"got {short(e.section_path)}  |  want {short(exp)}" for e, exp in bad_h])

    # 2. Body paths.
    body = [(e, exp) for e, exp in zip(elements, expected)
            if kind(e) not in ("heading", "title")]
    bad_b = [(e, exp) for e, exp in body if e.section_path != exp]
    line("OK" if not bad_b else "CHECK", "body paths match levels",
         f"{len(body) - len(bad_b)} of {len(body)}")

    # 3. Path depth: real hierarchy or flat/over-nested?
    depth = Counter(len(e.section_path) for e in elements)
    want = Counter(len(exp) for exp in expected)
    line("INFO", "path depth (got)", dict(sorted(depth.items())))
    line("INFO", "path depth (want)", dict(sorted(want.items())))

    # 4. Identifiers.
    structures = [e.metadata.get("structure", {}) for e in elements]
    types = Counter(s.get("structure_type")
                    for s in structures if s.get("identifier"))
    with_parent = sum(1 for s in structures if s.get("parent_identifier"))
    line("INFO", "identifiers by type", dict(types.most_common(6)))
    line("INFO", "elements with parent id",
         f"{with_parent} of {len(elements)}")

    # 5. Does the element path agree with the chunk's own heading path?
    #    (ComplianceChunker uses the element path first.)
    by_ref = {e.metadata.get("source_ref"): e for e in elements}
    disagree = []
    for c in parsed.chunk_candidates:
        first = next((by_ref[r] for r in c.source_refs
                      if r in by_ref and by_ref[r].section_path), None)
        if first is not None and first.section_path != list(c.headings):
            disagree.append((first.section_path, c.headings))
    line("OK" if not disagree else "CHECK", "element path = chunk path",
         f"{len(parsed.chunk_candidates) - len(disagree)} of {len(parsed.chunk_candidates)}")
    examples([f"element {short(a)}  |  chunk {short(b)}" for a, b in disagree])


def main():
    paths = sys.argv[1:] or DEFAULT_PATHS
    parser = DoclingParser()
    service = StructureInferenceService()
    for p in paths:
        run(p, parser, service)


if __name__ == "__main__":
    main()
