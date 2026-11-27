"""Stage 3 check: ComplianceChunker (+ splitter) on a cached Docling document.

Runs the real code in pipeline order:
    DoclingParser.parse_document -> JSON save/reload -> StructureInferenceService
    -> ComplianceChunker.chunk (as chunk_task does)
Short output: one line per check, a few examples where something needs a look.

Run from /app inside the worker:
    python -m tests.test_stage3_chunker
    python -m tests.test_stage3_chunker tests/data/cache/SOC2.docling.json
"""
import json
import re
import sys
from collections import Counter

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
TINY_TOKENS = 20
# Control / requirement IDs anywhere in the text (the chunker writes
# table rows as running text, so IDs are not at the start of a line).
ROW_ID = re.compile(r"\b((?:CC|A\.|PI|C|P)\d+(?:\.\d+)+)\b")


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
    structured = service.infer(reloaded)
    chunks = chunker.chunk(structured, parsed.chunk_candidates)
    elements = structured.elements
    tok = parser.chunk_tokenizer
    max_tokens = tok.get_max_tokens()

    # 1. Counts and the splitter.
    split = [c for c in chunks if c.metadata.get("split")]
    line("INFO", "chunks", f"{len(parsed.chunk_candidates)} candidates -> "
         f"{len(chunks)} chunks, {len(split)} made by the splitter")

    # 2. Size in tokens (what the embedder sees).
    sizes = [tok.count_tokens(c.text) for c in chunks]
    median = sorted(sizes)[len(sizes) // 2] if sizes else 0
    over = sum(s > max_tokens for s in sizes)
    tiny = [c.text for c, s in zip(chunks, sizes) if s < TINY_TOKENS]
    line("OK" if not (over or tiny) else "CHECK", "chunk sizes",
         f"median {median} tokens, over {max_tokens}: {over}, under {TINY_TOKENS}: {len(tiny)}")
    examples(tiny)

    # 3. Identity: one identifier per chunk is the goal.
    ids = [c.metadata.get("structural_identifiers") or [] for c in chunks]
    single = sum(1 for i in ids if len(i) == 1)
    none = sum(1 for i in ids if not i)
    multi = [(c, i) for c, i in zip(chunks, ids) if len(i) > 1]
    line("OK" if not multi else "CHECK", "chunk identity",
         f"one id: {single}, none: {none}, several: {len(multi)}")
    examples(
        [f"{c.section_path[-1][:40] if c.section_path else ''} -> {i[:5]}" for c, i in multi])
    types = Counter(c.structure_type for c in chunks)
    line("INFO", "structure types", dict(types.most_common(6)))

    # 4. Table chunks: how many control rows each one holds.
    table_chunks = [
        c for c in chunks
        if c.element_indexes
        and all(elements[i].element_type.name.lower() == "table" for i in c.element_indexes)
    ]
    rows = [c for c in table_chunks if c.metadata.get(
        "source") == "table_rows"]
    if rows:
        with_parent = sum(1 for c in rows if c.parent_identifier)
        line("INFO", "control row chunks",
             f"{len(rows)}, with id: {sum(1 for c in rows if c.identifier)}, "
             f"with parent: {with_parent}")
        sample = next((c for c in rows if c.identifier), rows[0])
        examples([f"{sample.identifier} (parent {sample.parent_identifier}): "
                  + " / ".join(sample.text.splitlines()[-3:])], 1)
    table_chunks = [c for c in table_chunks if c.metadata.get(
        "source") != "table_rows"]
    row_ids = [sorted(set(ROW_ID.findall(c.text))) for c in table_chunks]
    crowded = [(c, r) for c, r in zip(table_chunks, row_ids) if len(r) > 1]
    line("OK" if not crowded else "CHECK", "other table chunks",
         f"{len(table_chunks)} chunks, with several row IDs: {len(crowded)}, "
         f"max in one chunk: {max((len(r) for r in row_ids), default=0)}")
    examples([f"identity {c.structure_type}={c.identifier} but holds {r[:4]}"
              for c, r in crowded])
    # Why did these not become row chunks?
    for c, _ in crowded[:3]:
        parts = [elements[i] for i in c.element_indexes]
        kinds = Counter(e.element_type.name.lower() for e in parts)
        tables = [e for e in parts if e.table]
        id_rows = [sum(1 for row in e.table.rows if chunker._row_id(row))
                   for e in tables]
        firsts = [row[0][:18]
                  for e in tables for row in e.table.rows[:4] if row]
        print(f"           why: elements {dict(kinds)}, ID rows per table {id_rows}, "
              f"first cells {firsts}")
    labelled_wrong = sum(
        1 for c, r in crowded if c.structure_type != "control")
    if crowded:
        line("CHECK", "crowded chunks labelled section",
             f"{labelled_wrong} of {len(crowded)}")

    # 5. Paths and pages.
    no_path = sum(1 for c in chunks if not c.section_path)
    no_page = sum(1 for c in chunks if c.page_start is None)
    line("INFO", "chunks without path / page", f"{no_path} / {no_page}")

    # 6. Nothing lost, nothing unlinked.
    covered = {i for c in chunks for i in c.element_indexes}
    content = [i for i, e in enumerate(elements)
               if e.text and e.element_type.name.lower() != "heading"]
    missing = [elements[i].text for i in content if i not in covered]
    unmatched = sum(len(c.metadata.get("unmatched_source_refs") or [])
                    for c in chunks)
    line("OK" if not missing else "CHECK", "content covered by chunks",
         f"{len(content) - len(missing)} of {len(content)}, unlinked refs: {unmatched}")
    examples(missing)

    # 7. Splitter cuts: does a split part start or end mid-word?
    mid_word = [c.text for c in split
                if re.match(r"^[a-z]", c.text) or re.search(r"[A-Za-z]$", c.text)]
    if split:
        line("OK" if not mid_word else "CHECK", "splitter cuts mid-word",
             f"{len(mid_word)} of {len(split)}")


def main():
    paths = sys.argv[1:] or DEFAULT_PATHS
    parser = DoclingParser()
    service = StructureInferenceService()
    chunker = ComplianceChunker()
    for p in paths:
        run(p, parser, service, chunker)


if __name__ == "__main__":
    main()
