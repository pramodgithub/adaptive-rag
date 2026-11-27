"""Upload health report: is this document's chunking trustworthy?

Runs on the chunker's output, before anything is saved. Document-agnostic:
it checks shape (coverage, structure, identity, sizes), not content.

    fail   -> nothing is saved; the job fails with the reason
    review -> saved and searchable, but flagged for a look
    pass   -> nothing to do
"""
import re
from collections import Counter

from services.ingestion.chunking.chunker import ComplianceChunker
from services.ingestion.domain.elements import ElementType
from services.ingestion.parsers.docling_parser import DoclingParser

# Limits. Change here, not in the checks.
MIN_COVERAGE = 0.98          # share of content that must end up in chunks
MIN_PATH_SHARE = 0.50        # share of chunks with a section path
MAX_MULTI_ID_SHARE = 0.05    # share of chunks holding several identifiers
MAX_TINY_SHARE = 0.10        # share of chunks under TINY_CHARS
MAX_UNKNOWN_SHARE = 0.05     # share of elements with an unknown type
FLAT_MIN_HEADINGS = 10       # this many headings all on one level = flat
TINY_CHARS = 80
LARGE_CHARS = 3200


def _shape(token: str) -> str:
    """"§5" -> "§9", "Req.8.2" -> "A.9.9": what an unknown ID looks like."""
    return re.sub(r"\d+", "9", re.sub(r"[A-Za-z]+", "A", token))


def _unknown_shapes(elements) -> list[tuple[str, int]]:
    """Number-like starts of headings and table rows that no pattern knows.

    The most frequent shapes are the candidates for a new pattern.
    """
    shapes: Counter = Counter()

    for element in elements:
        starts = []

        if element.element_type == ElementType.HEADING:
            starts.append(element.text)
        elif element.table:
            starts.extend(row[0]
                          for row in element.table.rows if row and row[0])

        for text in starts:
            token = text.strip().split(" ")[0] if text.strip() else ""

            if not re.search(r"[\d§]", token):
                continue

            if DoclingParser._HEADING_PATTERN.match(text) or ComplianceChunker._ROW_ID.match(text):
                continue

            shapes[_shape(token)] += 1

    return shapes.most_common(5)


def build_health_report(document, candidates, chunks) -> dict:
    elements = document.elements
    headings = [e for e in elements if e.element_type == ElementType.HEADING]
    content = [
        index for index, e in enumerate(elements)
        if e.text and e.element_type != ElementType.HEADING
    ]
    covered = {index for chunk in chunks for index in chunk.element_indexes}
    missing = [index for index in content if index not in covered]

    n_chunks = len(chunks)
    def share(part, whole): return round(part / whole, 3) if whole else 0.0

    levels = Counter(h.metadata.get("heading_level") for h in headings)
    sizes = [len(chunk.text or "") for chunk in chunks]

    # Table chunks that still hold several ID rows: the row rule should
    # have split them.
    crowded = 0
    for chunk in chunks:
        if chunk.metadata.get("source") == "table_rows" or not chunk.element_indexes:
            continue
        parts = [elements[i] for i in chunk.element_indexes]
        if not all(part.table for part in parts):
            continue
        id_rows = sum(
            1 for part in parts for row in part.table.rows
            if ComplianceChunker._row_id(row)
        )
        if id_rows >= 2:
            crowded += 1

    metrics = {
        "elements": len(elements),
        "headings": len(headings),
        "heading_levels": dict(sorted(levels.items(), key=lambda kv: str(kv[0]))),
        "candidates": len(candidates),
        "chunks": n_chunks,
        "content_coverage": share(len(content) - len(missing), len(content)),
        "chunks_with_path": share(sum(1 for c in chunks if c.section_path), n_chunks),
        "chunks_with_id": share(sum(1 for c in chunks if c.identifier), n_chunks),
        "multi_id_chunks": share(
            sum(1 for c in chunks if len(c.metadata.get(
                "structural_identifiers") or []) > 1),
            n_chunks,
        ),
        "tiny_chunks": share(sum(1 for s in sizes if s < TINY_CHARS), n_chunks),
        "large_chunks": sum(1 for s in sizes if s > LARGE_CHARS),
        "unlinked_refs": sum(len(c.metadata.get("unmatched_source_refs") or []) for c in chunks),
        "crowded_table_chunks": crowded,
        "unknown_elements": share(
            sum(1 for e in elements if e.element_type ==
                ElementType.UNKNOWN), len(elements)
        ),
    }

    checks = [
        # name, level, passed
        ("has chunks", "fail", n_chunks > 0),
        ("content covered", "fail",
         metrics["content_coverage"] >= MIN_COVERAGE),
        ("structure not flat", "review",
         not (len(headings) >= FLAT_MIN_HEADINGS and len(levels) == 1)),
        ("chunks have a path", "review",
         not headings or metrics["chunks_with_path"] >= MIN_PATH_SHARE),
        ("one identifier per chunk", "review",
         metrics["multi_id_chunks"] <= MAX_MULTI_ID_SHARE),
        ("few tiny chunks", "review",
         metrics["tiny_chunks"] <= MAX_TINY_SHARE),
        ("no oversized chunks", "review", metrics["large_chunks"] == 0),
        ("chunks link to elements", "review", metrics["unlinked_refs"] == 0),
        ("ID tables split by row", "review",
         metrics["crowded_table_chunks"] == 0),
        ("element types known", "review",
         metrics["unknown_elements"] <= MAX_UNKNOWN_SHARE),
    ]

    failed = [(name, level) for name, level, passed in checks if not passed]
    if any(level == "fail" for _, level in failed):
        status = "fail"
    elif failed:
        status = "review"
    else:
        status = "pass"

    return {
        "status": status,
        "summary": "; ".join(name for name, _ in failed) or "all checks passed",
        "checks": [
            {"name": name, "level": level, "passed": passed}
            for name, level, passed in checks
        ],
        "metrics": metrics,
        "unknown_id_shapes": _unknown_shapes(elements),
        "missing_examples": [elements[i].text[:120] for i in missing[:3]],
    }
