"""Run the cached ingestion pipeline and print a readable entity report.

Usage (inside the worker container):
    python tests/test_cached_ingestion_pipeline.py
    python tests/test_cached_ingestion_pipeline.py "Article 6" CC6.1 "Lawfulness"

Options:
    --trace="Lawfulness of processing"   show that text at every pipeline stage
    --debug=CC1.5                        show every raw candidate for an id

Extra plain arguments are search terms: for each one the script shows the matching
entities (with full metadata) and the chunks whose text contains the term.
Use it to check whether an id exists in the chunks at all, or was lost earlier.
"""
import re
import sys
from collections import Counter, defaultdict
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
from services.ingestion.semantics.extractor import SemanticEntityExtractor
from services.ingestion.semantics.heading_labels import attach_heading_labels

from tests.fixtures.docling_cache import load_cached_document

TEST_FILES = [
    "tests/data/SOC2.docling.json",
    "tests/data/CELEX_32016R0679_EN_TXT.docling.json",
]


def build_canonical_document(parser: DoclingParser, document, path: str):
    elements = []

    for item, level in document.iterate_items():
        element = parser._convert_item(item=item, level=level)
        if element is not None:
            elements.append(element)

    return parser_canonical_document(parser, document, path, elements)


def parser_canonical_document(parser: DoclingParser, document, path: str, elements):
    from services.ingestion.domain.document import CanonicalDocument

    return CanonicalDocument(
        title=Path(path).name,
        elements=elements,
        page_count=parser._get_page_count(document),
        metadata={
            "source_format": "cached-docling",
            "parser": "docling",
        },
    )


def build_artifact(document, candidates):
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


def restore_candidates(parsed: dict) -> list[ChunkCandidate]:
    return [
        ChunkCandidate(
            text=item["text"],
            source_refs=item.get("source_refs", []),
            page_start=item.get("page_start"),
            page_end=item.get("page_end"),
            headings=item.get("headings", []),
        )
        for item in parsed.get("chunk_candidates", [])
    ]


# ------------------------------------------------------------------ report

def short(text, n=70):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def kind_of(entity):
    return entity.metadata["entity_key"].split(":", 1)[0]


def find_violations(entities):
    """Structural rules that must hold for ANY document. Empty list = healthy."""
    problems = []
    keys = [e.metadata["entity_key"] for e in entities]
    dups = [k for k, c in Counter(keys).items() if c > 1]
    if dups:
        problems.append(f"duplicate entity keys: {dups[:5]}")
    index = set(keys)
    for e in entities:
        if e.parent_identifier and (
            f"{kind_of(e)}:{e.parent_identifier.casefold()}" not in index
        ):
            problems.append(
                f"dangling parent: {e.identifier} -> {e.parent_identifier}")
        if e.title and (len(e.title) > 400 or "=" in e.title):
            problems.append(
                f"suspicious title on {e.identifier}: {short(e.title)}")
    for e in entities:
        container = e.metadata.get("container_key")
        if container and container not in index:
            problems.append(
                f"dangling container: {e.metadata['entity_key']} -> {container}")
    return problems


def label_of(e):
    return e.metadata.get("label") or kind_of(e)


def print_containment(entities, limit=40):
    """Chapter > Section > Article style tree, from document order (not from ids)."""
    defs = {e.metadata["entity_key"]: e for e in entities
            if e.metadata["candidate_kind"] == "definition"}
    children = defaultdict(list)
    for key, e in defs.items():
        c = e.metadata.get("container_key")
        if c in defs:
            children[c].append(e)
    roots = [e for k, e in defs.items() if k in children and e.metadata.get(
        "container_key") not in defs]
    if not roots:
        return
    print("\nCONTAINMENT (from document order)")
    printed = 0

    def walk(e, depth):
        nonlocal printed
        if printed >= limit:
            return
        kids = children.get(e.metadata["entity_key"], [])
        extra = f"  [{len(kids)} children]" if kids else ""
        print(
            f"  {'   ' * depth}{label_of(e)} {e.identifier}  {short(e.title or '(no title)', 50)}{extra}")
        printed += 1
        for k in kids[:6] if depth >= 1 else kids:
            walk(k, depth + 1)

    for r in roots:
        walk(r, 0)
    if printed >= limit:
        print(f"  ... (showing first {limit} lines)")


def print_sequence_gaps(entities, chunks):
    """Numbered ids should be roughly contiguous. Gaps = missed definitions."""
    by_label = defaultdict(set)
    scoped = set()
    for e in entities:
        label = e.metadata.get("label")
        if e.metadata["candidate_kind"] != "definition" or not label or not e.identifier.isdigit():
            continue
        if "@" in e.metadata["entity_key"]:
            scoped.add(label)
        by_label[label].add(int(e.identifier))
    cited = defaultdict(set)
    for e in entities:
        if e.metadata["candidate_kind"] == "reference" and e.metadata.get("label") and e.identifier.isdigit():
            cited[e.metadata["label"]].add(int(e.identifier))

    for label, ids in sorted(by_label.items()):
        if label in scoped or len(ids) < 5:
            continue
        top = max(ids)
        missing = [n for n in range(1, top + 1) if n not in ids]
        print(
            f"\nSEQUENCE CHECK  {label}: defined {len(ids)} of 1..{top}, missing {len(missing)}")
        if not missing:
            continue
        print(
            f"  missing: {missing[:40]}{' ...' if len(missing) > 40 else ''}")
        print(
            f"  of those, cited elsewhere as references: {sorted(set(missing) & cited[label])[:30]}")
        for n in missing[:3]:
            pat = re.compile(rf"{label}\s+{n}(?!\d)", re.IGNORECASE)
            hits = [c for c in chunks if pat.search(c.text)]
            print(f"  '{label} {n}' appears in {len(hits)} chunk(s)", end="")
            if hits:
                c = hits[0]
                m = pat.search(c.text)
                print(
                    f"; first: chunk {c.chunk_index} headings={c.metadata.get('headings', [])}")
                print(
                    f"      …{short(repr(c.text[max(0, m.start() - 100): m.end() + 120]), 240)}")
            else:
                print(" -> number is not in any chunk text (lost before extraction)")


def print_tree(entities, per_kind_limit=25):
    children = defaultdict(list)
    for e in entities:
        if e.metadata["candidate_kind"] == "definition":
            children[(kind_of(e), (e.parent_identifier or "").casefold())].append(e)

    for kind in sorted({k for k, _ in children}):
        print(f"\n  [{kind}]")
        printed = 0

        def walk(parent, depth):
            nonlocal printed
            for e in children.get((kind, parent), []):
                if printed >= per_kind_limit:
                    return
                print(
                    f"  {'   ' * depth}{e.identifier:<10} {short(e.title or '(no title)', 60)}")
                printed += 1
                walk(e.identifier.casefold(), depth + 1)

        walk("", 0)
        if printed >= per_kind_limit:
            print(f"  ... (showing first {per_kind_limit})")


def print_group(title, entities, line, limit=8):
    print(f"\n{title}: {len(entities)}")
    for e in entities[:limit]:
        print("  " + line(e))
    if len(entities) > limit:
        print(f"  ... and {len(entities) - limit} more")


def print_report(path, chunks, entities):
    defs = [e for e in entities if e.metadata["candidate_kind"] == "definition"]
    refs = [e for e in entities if e.metadata["candidate_kind"] == "reference"]

    print("\n" + "=" * 70)
    print(f"ENTITY REPORT  {Path(path).name}")
    print("=" * 70)
    print(f"chunks: {len(chunks)}")
    print(
        f"entities: {len(entities)}  (definitions {len(defs)}, reference-only {len(refs)})")
    print("by kind:", dict(Counter(kind_of(e) for e in entities)))
    print(
        f"definitions with a title: {sum(1 for e in defs if e.title)}/{len(defs)}")
    print(
        f"definitions with a description: {sum(1 for e in defs if 'description' in e.metadata)}/{len(defs)}")
    print(
        f"definitions with NEITHER (real gaps): {sum(1 for e in defs if not e.title and 'description' not in e.metadata)}/{len(defs)}")
    print("title came from:", dict(Counter(e.metadata.get("title_source")
          for e in defs if e.title)))
    print(
        f"entities with a resolved parent: {sum(1 for e in entities if e.parent_identifier)}")

    problems = find_violations(entities)
    print("\nINVARIANTS:",
          "OK" if not problems else f"{len(problems)} PROBLEM(S)")
    for p in problems[:10]:
        print("  !", p)

    print("\nHIERARCHY (dotted ids, definitions only)")
    print_tree(entities)
    print_containment(entities)
    print_sequence_gaps(entities, chunks)

    print_group(
        "DEFINITIONS WITH NEITHER TITLE NOR DESCRIPTION (real gaps; run with the id as a search term)",
        [e for e in defs if not e.title and "description" not in e.metadata],
        lambda e: f"{e.metadata['entity_key']:<14} chunk {e.metadata['definition_chunks']} via {e.metadata['extraction_method']}",
    )
    print_group(
        "REFERENCE-ONLY (cited but never defined in this document)",
        refs,
        lambda e: f"{e.identifier:<10} cited in chunks {e.metadata.get('reference_chunks', [])[:6]}",
    )
    print_group(
        "MISSING INTERMEDIATE LEVEL (e.g. A1.2.1.1 exists but A1.2.1 does not)",
        [e for e in entities if "parent_hint" in e.metadata],
        lambda e: f"{e.identifier:<10} expected {e.metadata['parent_hint']}",
    )
    print_group(
        "UNCORROBORATED (low confidence, likely noise)",
        [e for e in entities if not e.metadata["corroborated"]],
        lambda e: f"{e.identifier:<10} conf {e.confidence}  {short(e.title or '', 40)}",
    )
    print_group(
        "LOWEST CONFIDENCE DEFINITIONS",
        sorted(defs, key=lambda e: e.confidence),
        lambda e: f"{e.identifier:<10} conf {e.confidence}  {e.metadata['extraction_method']}  {short(e.title or '', 40)}",
        limit=5,
    )


def inspect_terms(terms, chunks, entities):
    for term in terms:
        print("\n" + "-" * 70)
        print(f"INSPECT: {term!r}")
        needle = term.casefold()

        def haystack(e):
            label = e.metadata.get("label") or ""
            return " ".join([
                e.identifier, f"{label} {e.identifier}", e.title or "",
                e.metadata["entity_key"].replace(":", " "),
            ]).casefold()

        hits = [e for e in entities if needle in haystack(e)]
        print(f"entities matching: {len(hits)}")
        for e in hits[:5]:
            print(f"  {e.identifier} [{e.entity_type.value}] conf={e.confidence} "
                  f"parent={e.parent_identifier} title={short(e.title or None, 60)}")
            print(
                f"    metadata: { {k: (short(v, 80) if isinstance(v, str) else v) for k, v in e.metadata.items()} }")

        pattern = re.compile(re.escape(term).replace(
            r"\ ", r"\s+"), re.IGNORECASE)
        matching = [c for c in chunks if pattern.search(c.text)]
        print(f"chunks whose text contains it: {len(matching)}")
        for c in matching[:3]:
            m = pattern.search(c.text)
            start = max(0, m.start() - 80)
            print(
                f"  chunk {c.chunk_index} headings={c.metadata.get('headings', [])}")
            print(f"    …{short(repr(c.text[start:m.end() + 160]), 260)}")


def trace_term(term, canonical, structured, candidates):
    """Show where a piece of text lives at each pipeline stage (finds where ids get lost)."""
    pat = re.compile(re.escape(term), re.IGNORECASE)
    print("\n" + "-" * 70)
    print(f"TRACE: {term!r} through the pipeline stages")
    for name, doc in (("parsed elements", canonical), ("after structure inference", structured)):
        elements = list(getattr(doc, "elements", None) or [])
        texts = [(getattr(el, "text", "") or "") for el in elements]
        exact = [i for i, t in enumerate(
            texts) if t.strip().casefold() == term.casefold()]
        loose = [i for i, t in enumerate(texts) if pat.search(t)]
        print(
            f"\n[{name}] {len(elements)} elements; exact-text matches {len(exact)}, containing it {len(loose)}")
        for i in (exact or loose)[:2]:
            for j in range(max(0, i - 3), min(len(elements), i + 4)):
                el = elements[j]
                et = getattr(getattr(el, "element_type", None),
                             "value", getattr(el, "element_type", None))
                mark = ">>" if j == i else "  "
                print(
                    f" {mark} #{j} {str(et):<14} {short(repr(texts[j]), 60):<64} path={short(getattr(el, 'section_path', None), 60)}")
    hits = [c for c in candidates if pat.search(c.text)]
    print(f"\n[chunk candidates] {len(hits)} contain it")
    for c in hits[:2]:
        m = pat.search(c.text)
        print(f"   headings={c.headings}")
        print(
            f"   ...{short(repr(c.text[max(0, m.start() - 100): m.end() + 100]), 240)}")


def debug_candidates(term, chunks, extractor):
    """Every raw candidate for an id, plus the unabridged text that follows it."""
    needle = term.casefold()
    print("\n" + "-" * 70)
    print(f"DEBUG candidates for {term!r}")
    shown = 0
    for i, chunk in enumerate(chunks):
        nxt = chunks[i + 1] if i + 1 < len(chunks) else None
        for c in extractor.extract_candidates(chunk, next_chunk=nxt):
            if needle not in c.display.casefold() and needle not in c.key:
                continue
            print(f"chunk {c.chunk_index:<4} {c.evidence.name:<10} src={c.title_source:<10} "
                  f"title={short(c.title, 60)!r} desc={short(c.description, 40)!r}")
            pos = chunk.text.find(c.display)
            if pos >= 0 and shown < 4:
                print(
                    f"   raw text after id: {chunk.text[pos + len(c.display): pos + len(c.display) + 300]!r}")
            shown += 1
            if shown >= 10:
                return


def run(path: str, terms, traces=(), debugs=()):
    print(path)

    parser = DoclingParser()
    docling_document = load_cached_document(path)
    parser._normalize_docling_document(docling_document)
    candidates = parser._build_chunk_candidates(docling_document)

    canonical = build_canonical_document(parser, docling_document, path)
    artifact = build_artifact(canonical, candidates)

    restored_document = document_from_dict(artifact)
    restored_candidates = restore_candidates(artifact)

    structured_document = StructureInferenceService().infer(restored_document)
    chunks = ComplianceChunker().chunk(structured_document, restored_candidates)

    extractor = SemanticEntityExtractor()
    merged = attach_heading_labels(structured_document, chunks, extractor)
    print(
        f"\nlabel-only headings re-attached (e.g. 'Article 6' + title): {merged} chunk(s)")
    entities = extractor.extract_document(chunks, framework=Path(path).stem)

    print_report(path, chunks, entities)
    if terms:
        inspect_terms(terms, chunks, entities)
    for term in traces:
        trace_term(term, canonical, structured_document, candidates)
    for term in debugs:
        debug_candidates(term, chunks, extractor)


if __name__ == "__main__":
    args = sys.argv[1:]
    search_terms = [a for a in args if not a.startswith("--")]
    trace_terms = [a.split("=", 1)[1]
                   for a in args if a.startswith("--trace=")]
    debug_terms = [a.split("=", 1)[1]
                   for a in args if a.startswith("--debug=")]
    for test_file in TEST_FILES:
        run(test_file, search_terms, trace_terms, debug_terms)
