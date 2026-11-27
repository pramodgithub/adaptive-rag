"""Stage 4 check: the graph tree GraphService would write, on a cached document.

Runs the real code in pipeline order, then GraphService.build_tree.
No Neo4j needed: it checks the plain node and link lists.

Run from /app inside the worker:
    python -m tests.test_stage4_graph
"""
import json
import sys
from collections import Counter

from services.graph.graph_service import GraphService
from services.ingestion.chunking.chunker import ComplianceChunker
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


def run(path, parser, service, chunker):
    name = path.rsplit("/", 1)[-1]
    print(f"\n=== {name} ===")
    parsed = parser.parse_document(load_cached_document(path), name)
    reloaded = document_from_dict(
        json.loads(json.dumps(document_to_dict(
            parsed.canonical), ensure_ascii=False))
    )
    chunks = chunker.chunk(service.infer(reloaded), parsed.chunk_candidates)
    tree = GraphService.build_tree("test-version", chunks)

    sections = tree["sections"]
    links = tree["links"]
    counts = tree["counts"]
    line("INFO", "nodes and links", counts)

    # 1. Tree shape.
    depth = Counter(s["depth"] for s in sections)
    line("INFO", "sections by depth", dict(sorted(depth.items())))
    tops = [s["title"][:30] for s in sections if s["depth"] == 1]
    line("INFO", "top sections", f"{len(tops)}: {tops[:4]}")

    # 2. Every section except the top ones has a parent.
    ids = {s["id"] for s in sections}
    children = {l["target"] for l in links["HAS_SUBSECTION"]}
    orphans = [s["title"]
               for s in sections if s["depth"] > 1 and s["id"] not in children]
    line("OK" if not orphans else "CHECK", "sections with a parent",
         f"{len(sections) - len(tops) - len(orphans)} of {len(sections) - len(tops)}")
    examples(orphans)

    # 3. Every chunk with a path sits in a section that exists.
    in_section = {l["source"]
                  for l in links["IN_SECTION"] if l["target"] in ids}
    with_path = [c for c in tree["chunks"] if c["section_path"]]
    line("OK" if len(in_section) == len(with_path) else "CHECK", "chunks placed in a section",
         f"{len(in_section)} of {len(with_path)} (no path: {len(tree['chunks']) - len(with_path)})")

    # 4. Section identity (Article 32 section gets "32").
    named = Counter(s["structure_type"] for s in sections if s["identifier"])
    line("INFO", "sections with an identifier", dict(named.most_common(5)))

    # 5. Control hierarchy: parents found, no loops.
    controls = [c for c in tree["chunks"] if c["structure_type"] == "control"]
    want_parent = [c for c in controls
                   if c["parent_identifier"] and "." in c["parent_identifier"]]
    part_of = {l["source"]: l["target"] for l in links["PART_OF"]}
    missing = [c["identifier"] for c in want_parent if c["id"] not in part_of]
    line("OK" if not missing else "CHECK", "controls linked to parent",
         f"{len(part_of)} links; dotted parents not found: {len(missing)}")
    examples(missing)

    loops = 0
    for start in part_of:
        seen, node = set(), start
        while node in part_of:
            if node in seen:
                loops += 1
                break
            seen.add(node)
            node = part_of[node]
    line("OK" if not loops else "CHECK", "control loops", loops)

    # 6. Reading order.
    line("OK" if counts["next"] == len(tree["chunks"]) - 1 else "CHECK",
         "reading order links", f"{counts['next']} for {len(tree['chunks'])} chunks")

    # 7. One sample branch, read like a table of contents.
    deepest = max(sections, key=lambda s: s["depth"], default=None)
    if deepest:
        line("INFO", "sample branch", " > ".join(
            p[:26] for p in deepest["path"]))


def main():
    paths = sys.argv[1:] or DEFAULT_PATHS
    parser = DoclingParser()
    service = StructureInferenceService()
    chunker = ComplianceChunker()
    for p in paths:
        run(p, parser, service, chunker)


if __name__ == "__main__":
    main()
