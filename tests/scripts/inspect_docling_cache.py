"""Inspect cached Docling documents: structure, tables, targets and chunks.

Run from /app inside the worker:
    python -m tests.inspect_docling_cache                 # both cached docs
    python -m tests.inspect_docling_cache --chunk         # + production chunker
    python -m tests.inspect_docling_cache --dump-table 0 3
"""
import argparse
import os
import re
from collections import Counter, defaultdict

from tests.fixtures.docling_cache import load_cached_document

DEFAULT_TARGETS = [r"Article\s+32", r"CC6\.1\.4", r"CC6\.1\.5", r"CC6\.1\.6"]
SMALL_CHUNK_TOKENS = 20  # chunks below this are usually fragments


def pages_of(item):
    """All pages an item touches (not just the first)."""
    return sorted({p.page_no for p in (getattr(item, "prov", None) or [])})


def page_of(item):
    pages = pages_of(item)
    return pages[0] if pages else None


def label_of(item):
    label = getattr(item, "label", "?")
    return getattr(label, "value", str(label))


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

    labels = Counter(label_of(t) for t in texts)
    print("  text labels        :", dict(labels.most_common()))

    layers = Counter(
        getattr(getattr(t, "content_layer", None), "value", "n/a") for t in texts
    )
    print("  content layers     :", dict(layers))
    print("    (non-body layers, e.g. furniture, are skipped by export and chunker)")

    per_page = defaultdict(int)
    for it in texts + tables + pictures:
        for p in pages_of(it):
            per_page[p] += 1
    all_pages = sorted(getattr(doc, "pages", {}).keys())
    empty = [p for p in all_pages if per_page[p] == 0]
    print(f"  pages with 0 items : {empty if empty else 'none'}")


# ---------- 2. structure (what the graph tree depends on) ----------
def structure(doc):
    from docling_core.types.doc import SectionHeaderItem

    print("\n[2] STRUCTURE")
    class_label = Counter()
    parents = Counter()
    multi_page = []
    headings = []

    for item, depth in doc.iterate_items():
        class_label[(type(item).__name__, label_of(item))] += 1
        parent = getattr(item, "parent", None)
        parents[parent.cref if parent else None] += 1
        if len(pages_of(item)) > 1:
            multi_page.append(item)
        if isinstance(item, SectionHeaderItem):
            headings.append((item.level, depth, page_of(item), item.text))

    print("  class -> label (class name alone can't separate these):")
    for (cls, label), n in sorted(class_label.items()):
        print(f"    {cls:20} {label:20} {n}")

    print("  top parents (mostly '#/body' = flat tree, hierarchy must come "
          "from headings):")
    for ref, n in parents.most_common(5):
        print(f"    {ref}: {n}")

    levels = Counter(h[0] for h in headings)
    print(f"  section headings   : {len(headings)}, levels used: "
          f"{dict(sorted(levels.items()))}")
    if headings and len(levels) == 1:
        print("    -> every heading has the same level: Docling gave no "
              "hierarchy, a fallback is needed")
    for level, depth, page, text in headings[:25]:
        print(f"    H{level} depth={depth} page={page}  {snippet(text, 70)}")
    if len(headings) > 25:
        print(f"    ... {len(headings) - 25} more")

    print(f"  items spanning >1 page: {len(multi_page)}")
    for it in multi_page[:5]:
        print(f"    {it.self_ref} {label_of(it)} pages={pages_of(it)}")


# ---------- 3. tables ----------
def row_text(table, r):
    cells = [
        c for c in table.data.table_cells
        if c.start_row_offset_idx <= r < c.end_row_offset_idx
    ]
    cells.sort(key=lambda c: c.start_col_offset_idx)
    return " | ".join(snippet(c.text, 80) for c in cells)


def table_summary(doc):
    print("\n[3] TABLES")
    for i, t in enumerate(getattr(doc, "tables", [])):
        d = t.data
        header_rows = sorted({
            r for c in d.table_cells if c.column_header
            for r in range(c.start_row_offset_idx, c.end_row_offset_idx)
        })
        print(f"  table {i:<3} pages={pages_of(t)} rows={d.num_rows} "
              f"cols={d.num_cols} cells={len(d.table_cells)} "
              f"header_rows={header_rows or 'none'}")


def dump_table(doc, index, max_rows=15):
    t = doc.tables[index]
    print(f"\n  --- table {index} (first {max_rows} rows) ---")
    for r in range(min(t.data.num_rows, max_rows)):
        print(f"  r{r:<3} {row_text(t, r)}")


# ---------- 4. pictures ----------
def picture_summary(doc):
    print("\n[4] PICTURES")
    pictures = list(getattr(doc, "pictures", []))
    if not pictures:
        print("  none")
    for p in pictures:
        print(f"  {p.self_ref} pages={pages_of(p)} "
              f"caption='{snippet(p.caption_text(doc), 70)}'")


# ---------- 5. where do targets live ----------
def find_targets(doc, targets):
    print("\n[5] WHERE TARGETS LIVE")
    for pat in targets:
        print(f"\n  pattern: {pat}")
        rx = re.compile(pat, re.IGNORECASE)
        found = False

        for t in getattr(doc, "texts", []):
            if rx.search(t.text or ""):
                found = True
                print(f"    TEXT   label={label_of(t)} pages={pages_of(t)} "
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
                    print(f"    TABLE  #{ti} pages={pages_of(tbl)} row={r} "
                          f"col={c.start_col_offset_idx}")
                    print(f"           full row: {row_text(tbl, r)}")

        if not found:
            print("    NOT FOUND in texts or tables  -> Docling dropped it")


def markdown_context(doc, targets, width=250):
    print("\n[6] MARKDOWN EXPORT CONTEXT")
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


# ---------- 7. chunks, using the production parser ----------
def chunk_view(doc, targets):
    # Use the real parser so the test can't drift from production
    # (same tokenizer, max_tokens, chunker settings and normalization).
    from services.ingestion.parsers.docling_parser import DoclingParser

    parser = DoclingParser()
    parser._normalize_docling_document(doc)  # production normalizes first
    chunker = parser.chunker
    tok = parser.chunk_tokenizer
    max_tokens = tok.get_max_tokens()

    chunks = list(chunker.chunk(doc))
    print(f"\n[7] CHUNKS (production settings, max_tokens={max_tokens})")
    print(f"  total chunks: {len(chunks)}")

    sizes, over, small, no_heading = [], [], [], 0
    for i, ch in enumerate(chunks):
        n = tok.count_tokens(chunker.contextualize(ch))
        sizes.append(n)
        if n > max_tokens:
            over.append((i, n))
        if n < SMALL_CHUNK_TOKENS:
            small.append((i, n))
        if not getattr(ch.meta, "headings", None):
            no_heading += 1

    if sizes:
        sizes_sorted = sorted(sizes)
        print(f"  tokens min/median/max: {sizes_sorted[0]} / "
              f"{sizes_sorted[len(sizes) // 2]} / {sizes_sorted[-1]}")
    print(f"  over max_tokens  : {len(over)} {over[:10]}")
    print(f"  tiny (<{SMALL_CHUNK_TOKENS} tok)   : {len(small)} {small[:10]}")
    print(f"  without headings : {no_heading}")

    for pat in targets:
        rx = re.compile(pat, re.IGNORECASE)
        hits = []
        for i, ch in enumerate(chunks):
            text = chunker.contextualize(ch)
            if rx.search(text):
                hits.append((i, ch, text))
        print(f"\n  pattern: {pat} -> {len(hits)} chunk(s)")
        for i, ch, text in hits[:3]:
            labels = [label_of(di) for di in getattr(ch.meta, "doc_items", [])]
            print(f"    chunk {i}: {sizes[i]} tokens, "
                  f"headings={getattr(ch.meta, 'headings', None)}")
            print(f"      doc_item labels: {labels}")
            print(f"      text: {snippet(text, 300)}")


def run(path, targets, do_chunk, dump_tables):
    print("\n" + "=" * 80)
    print(f"DOCUMENT: {os.path.basename(path)}")
    print("=" * 80)
    doc = load_cached_document(path)

    overview(doc)
    structure(doc)
    table_summary(doc)
    for ti in dump_tables:
        if ti < len(doc.tables):
            dump_table(doc, ti)
    picture_summary(doc)
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
                    help="also run the production chunker (loads the tokenizer)")
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
