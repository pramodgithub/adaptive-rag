import argparse
import os
import re
from collections import Counter, defaultdict

from tests.fixtures.docling_cache import load_cached_document

DEFAULT_TARGETS = [r"Article\s+32", r"CC6\.1\.4", r"CC6\.1\.5", r"CC6\.1\.6"]
MAX_TOKENS = 700


def page_of(item):
    prov = getattr(item, "prov", None) or []
    return prov[0].page_no if prov else None


def snippet(text, n=160):
    return re.sub(r"\s+", " ", text or "").strip()[:n]


# ---------- 1. overview ----------
def overview(doc):
    texts = list(getattr(doc, "texts", []))
    tables = list(getattr(doc, "tables", []))
    pictures = list(getattr(doc, "pictures", []))

    print("\n[1] OVERVIEW")
    print(f"  pages in doc.pages : {len(getattr(doc, 'pages', {}))}")
    print(f"  text items         : {len(texts)}")
    print(f"  tables             : {len(tables)}")
    print(f"  pictures           : {len(pictures)}")

    labels = Counter(str(getattr(t, "label", "?")) for t in texts)
    print("  text labels        :", dict(labels.most_common()))

    layers = Counter(str(getattr(t, "content_layer", "n/a")) for t in texts)
    print("  content layers     :", dict(layers))
    print("    (non-body layers, e.g. furniture, are skipped by export and chunker)")

    # pages with nothing extracted
    per_page = defaultdict(int)
    for it in texts + tables + pictures:
        p = page_of(it)
        if p is not None:
            per_page[p] += 1
    all_pages = sorted(getattr(doc, "pages", {}).keys())
    empty = [p for p in all_pages if per_page[p] == 0]
    print(f"  pages with 0 items : {empty if empty else 'none'}")


# ---------- 2. tables ----------
def row_text(table, r):
    cells = [
        c for c in table.data.table_cells
        if c.start_row_offset_idx <= r < c.end_row_offset_idx
    ]
    cells.sort(key=lambda c: c.start_col_offset_idx)
    return " | ".join(snippet(c.text, 80) for c in cells)


def table_summary(doc):
    print("\n[2] TABLES")
    for i, t in enumerate(getattr(doc, "tables", [])):
        d = t.data
        print(f"  table {i:<3} page={page_of(t)} rows={d.num_rows} "
              f"cols={d.num_cols} cells={len(d.table_cells)}")


def dump_table(doc, index, max_rows=15):
    t = doc.tables[index]
    print(f"\n  --- table {index} (first {max_rows} rows) ---")
    for r in range(min(t.data.num_rows, max_rows)):
        print(f"  r{r:<3} {row_text(t, r)}")


# ---------- 3. where do targets live ----------
def find_targets(doc, targets):
    print("\n[3] WHERE TARGETS LIVE")
    for pat in targets:
        print(f"\n  pattern: {pat}")
        rx = re.compile(pat, re.IGNORECASE)
        found = False

        for t in getattr(doc, "texts", []):
            if rx.search(t.text or ""):
                found = True
                print(f"    TEXT   label={t.label} page={page_of(t)} "
                      f"ref={t.self_ref}")
                print(f"           {snippet(t.text, 200)}")

        for ti, tbl in enumerate(getattr(doc, "tables", [])):
            seen_rows = set()
            for c in tbl.data.table_cells:
                if rx.search(c.text or ""):
                    r = c.start_row_offset_idx
                    if r in seen_rows:
                        continue
                    seen_rows.add(r)
                    found = True
                    print(f"    TABLE  #{ti} page={page_of(tbl)} row={r} "
                          f"col={c.start_col_offset_idx}")
                    print(f"           full row: {row_text(tbl, r)}")

        if not found:
            print("    NOT FOUND in texts or tables  -> Docling dropped it")


def markdown_context(doc, targets, width=250):
    print("\n[4] MARKDOWN EXPORT CONTEXT (what HybridChunker conceptually sees)")
    md = doc.export_to_markdown()
    for pat in targets:
        m = re.search(pat, md, re.IGNORECASE)
        print(f"\n  pattern: {pat}")
        if not m:
            print("    not in markdown export")
            continue
        s = max(0, m.start() - width)
        e = min(len(md), m.end() + width)
        print("    " + md[s:e].replace("\n", "\n    "))


# ---------- 4. chunks ----------
def chunk_view(doc, targets):
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import (
        HuggingFaceTokenizer,
    )
    from transformers import AutoTokenizer

    tok = HuggingFaceTokenizer(
        tokenizer=AutoTokenizer.from_pretrained("google/gemma-2-9b-it"),
        max_tokens=MAX_TOKENS,
    )
    chunker = HybridChunker(
        tokenizer=tok, repeat_table_header=True,
        merge_peers=True, always_emit_headings=False,
    )

    print("\n[5] CHUNKS CONTAINING TARGETS")
    chunks = list(chunker.chunk(doc))
    print(f"  total chunks: {len(chunks)}")

    for pat in targets:
        rx = re.compile(pat, re.IGNORECASE)
        hits = []
        for i, ch in enumerate(chunks):
            text = chunker.contextualize(ch)
            if rx.search(text):
                hits.append((i, ch, text))
        print(f"\n  pattern: {pat} -> {len(hits)} chunk(s)")
        for i, ch, text in hits[:3]:
            labels = [str(getattr(di, "label", "?"))
                      for di in getattr(ch.meta, "doc_items", [])]
            print(f"    chunk {i}: {len(text)} chars, "
                  f"headings={getattr(ch.meta, 'headings', None)}")
            print(f"      doc_item labels: {labels}")
            print(f"      text: {snippet(text, 300)}")


def run(path, targets, do_chunk, dump_tables):
    print("\n" + "=" * 80)
    print(f"DOCUMENT: {os.path.basename(path)}")
    print("=" * 80)
    doc = load_cached_document(path)

    overview(doc)
    table_summary(doc)
    for ti in dump_tables:
        if ti < len(doc.tables):
            dump_table(doc, ti)
    find_targets(doc, targets)
    markdown_context(doc, targets)
    if do_chunk:
        chunk_view(doc, targets)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=[
        "tests/data/cache/CELEX_32016R0679_EN_TXT.docling.json",
        "tests/data/cache/SOC2.docling.json",
    ])
    ap.add_argument("--targets", nargs="*", default=DEFAULT_TARGETS)
    ap.add_argument("--chunk", action="store_true",
                    help="also run HybridChunker (loads the tokenizer, slower)")
    ap.add_argument("--dump-table", type=int, nargs="*", default=[],
                    help="print the grid of these table indexes")
    a = ap.parse_args()

    for p in a.paths:
        if not os.path.exists(p):
            print(f"ERROR: missing {p}")
            continue
        run(p, a.targets, a.chunk, a.dump_table)


if __name__ == "__main__":
    main()
