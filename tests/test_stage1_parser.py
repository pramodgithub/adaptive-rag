"""Stage 1 check: DoclingParser on a cached Docling document.

Runs the real parser code (parse_document). No PDF, no conversion.
Short output: one line per check, a few examples only when something needs a look.

Run from /app inside the worker:
    python -m tests.test_stage1_parser
    python -m tests.test_stage1_parser tests/data/cache/SOC2.docling.json
"""
import re
import sys
from collections import Counter

from services.ingestion.normalization.text_normalizer import normalize_text
from services.ingestion.parsers.docling_parser import DoclingParser
from tests.fixtures.docling_cache import load_cached_document

DEFAULT_PATHS = [
    "tests/data/cache/gdpr.docling.json",
    "tests/data/cache/SOC2.docling.json",
]

# Common compliance numbering (regulations, standards, audit reports).
HEADING_LIKE = re.compile(
    r"^(Article|Section|Clause|Chapter|Part|Annex|Appendix|Schedule)\s+[\dIVXLC]+\b"
    r"|^(CC|A\.|PI|C|P)\d+(\.\d+)+\b"
    r"|^\d+(\.\d+)+\s+\S",
    re.IGNORECASE,
)
BIDI = re.compile("[‪-‮⁦-⁩]")
TINY_TOKENS = 20


def line(status, name, detail=""):
    print(f"  [{status:5}] {name:30} {detail}")


def examples(items, n=3):
    for text in items[:n]:
        print(f"           e.g. {text[:90]!r}")


def run(path, parser):
    print(f"\n=== {path.rsplit('/', 1)[-1]} ===")
    doc = load_cached_document(path)
    parsed = parser.parse_document(doc, path.rsplit("/", 1)[-1])
    elements = parsed.canonical.elements

    ref_to_item = {item.self_ref: item for item, _ in doc.iterate_items()}

    def docling_label(el):
        item = ref_to_item.get(el.metadata.get("source_ref"))
        return getattr(getattr(item, "label", None), "value", "?")

    # 1. Types: what the parser called it vs what Docling knows it is.
    pairs = Counter((docling_label(e), e.element_type.name.lower())
                    for e in elements)
    wrong = {
        (lbl, typ): n for (lbl, typ), n in pairs.items()
        if (lbl, typ) not in {
            ("text", "paragraph"), ("paragraph", "paragraph"),
            ("section_header", "heading"), ("title", "title"),
            ("list_item", "list"), ("table", "table"),
            ("picture", "image"), ("chart", "image"),
            ("footnote", "footnote"), ("caption", "paragraph"),
            ("code", "paragraph"), ("formula", "paragraph"),
            ("reference", "paragraph"),
        }
    }
    line("OK" if not wrong else "CHECK", "element types",
         f"{len(elements)} elements" + (f", mismatches: {wrong}" if wrong else ""))

    # 2. Heading levels: kept on every heading, and more than one level.
    headings = [e for e in elements if e.element_type.name.lower()
                == "heading"]
    levels = Counter(h.metadata.get("heading_level") for h in headings)
    stored = sum(1 for h in headings if h.metadata.get("heading_level"))
    source = {h.metadata.get("heading_level_source") for h in headings}
    good = headings and stored == len(headings) and len(levels) > 1
    line("OK" if good else "CHECK", "heading levels",
         f"{len(headings)} headings, level stored on {stored}, "
         f"levels {dict(sorted(levels.items(), key=lambda kv: str(kv[0])))}, "
         f"source {source}")
    joined = [h.text for h in headings if h.metadata.get("joined_title")]
    line("INFO", "number + title joined", f"{len(joined)}")
    examples(joined, 2)

    # 3. Headings Docling missed (tagged as plain text / list).
    missed = [
        e.text for e in elements
        if e.element_type.name.lower() in ("paragraph", "list")
        and len(e.text) <= 120
        and HEADING_LIKE.match(e.text)
        and not e.text.rstrip().endswith((".", ";", ","))
    ]
    groups = Counter(t.split()[0].rstrip(".:") for t in missed)
    line("OK" if not missed else "CHECK", "possible missed headings",
         f"{len(missed)}, by first word: {dict(groups.most_common(8))}")
    examples(missed)
    promoted = [e.text for e in headings if e.metadata.get("promoted_heading")]
    pgroups = Counter(t.split()[0].rstrip(".:") for t in promoted)
    line("INFO", "headings promoted by parser",
         f"{len(promoted)}, by first word: {dict(pgroups.most_common(8))}")

    # 4. Tables: contents pages and header guesses.
    tables = [e for e in elements if e.element_type.name.lower() == "table"]
    toc = [t for t in tables if docling_label(t) == "document_index"]
    no_header = []
    for t in tables:
        item = ref_to_item.get(t.metadata.get("source_ref"))
        cells = getattr(getattr(item, "data", None), "table_cells", []) or []
        if not any(c.column_header for c in cells):
            no_header.append(t)
    line("OK" if not toc else "CHECK", "contents page kept as table",
         f"{len(toc)} of {len(tables)} tables")
    continued = [t for t in tables if t.metadata.get("continued_table")]
    wrong_header = [
        t for t in tables
        if bool(t.table and t.table.headers) != (t not in no_header)
    ]
    line("OK" if not no_header else "CHECK", "tables with no header",
         f"{len(no_header)} of {len(tables)} (after carrying headers over)")
    line("INFO", "continued tables given a header", f"{len(continued)}")
    line("OK" if not wrong_header else "CHECK", "element header matches Docling",
         f"{len(wrong_header)} mismatches")

    # 5. Pages: items on more than one page get only the first.
    multi = [
        e for e in elements
        if len({p.page_no for p in getattr(
            ref_to_item.get(e.metadata.get("source_ref")), "prov", []) or []}) > 1
    ]
    line("OK" if not multi else "CHECK", "multi-page items (end page lost)",
         f"{len(multi)}")

    # 6. Images: no searchable text.
    images = [e for e in elements if e.element_type.name.lower() == "image"]
    empty_imgs = [e for e in images if not e.text]
    line("OK" if not empty_imgs else "CHECK", "images with no text",
         f"{len(empty_imgs)} of {len(images)}")

    # 7. Text cleaning.
    dirty = [e.text for e in elements if BIDI.search(e.text or "")]
    padded = [e.text for e in elements if e.text and e.text != e.text.strip()]
    line("OK" if not (dirty or padded) else "CHECK", "text cleaning",
         f"hidden marks {len(dirty)}, leading/trailing spaces {len(padded)}")
    doc_texts = [item.text for item, _ in doc.iterate_items()
                 if getattr(item, "text", None)
                 and getattr(getattr(item, "label", None), "value", None) != "code"]
    doc_bad = [t for t in doc_texts
               if BIDI.search(t) or t != t.strip() or "  " in t]
    line("OK" if not doc_bad else "CHECK", "text cleaning (chunk source)",
         f"{len(doc_bad)} of {len(doc_texts)} items with marks or extra spaces")
    examples(doc_bad, 2)

    # 8. Chunk candidates made inside the parser.
    tok = parser.chunk_tokenizer
    max_tokens = tok.get_max_tokens()
    sizes = [tok.count_tokens(c.text) for c in parsed.chunk_candidates]
    median = sorted(sizes)[len(sizes) // 2] if sizes else 0
    over = sum(s > max_tokens for s in sizes)
    tiny = sum(s < TINY_TOKENS for s in sizes)
    line("OK" if not (over or tiny) else "CHECK", "chunk candidates",
         f"{len(sizes)} chunks, median {median} tokens, "
         f"over {max_tokens}: {over}, under {TINY_TOKENS}: {tiny}")
    # 9. Nothing lost: every element must sit in at least one chunk.
    # Headings are not chunk content: the chunker puts them in each
    # chunk's heading path instead. So check them there.
    in_chunks = {ref for c in parsed.chunk_candidates for ref in c.source_refs}
    content = [e for e in elements
               if e.text and e.element_type.name.lower() != "heading"]
    missing = [e for e in content if e.metadata.get(
        "source_ref") not in in_chunks]
    line("OK" if not missing else "CHECK", "content covered by chunks",
         f"{len(content) - len(missing)} of {len(content)}")
    examples([f"{e.element_type.name.lower()}: {e.text}" for e in missing])

    in_paths = {h for c in parsed.chunk_candidates for h in c.headings}
    unused = [h.text for h in headings if h.text not in in_paths]
    line("OK" if len(unused) <= 2 else "CHECK", "headings used in chunk paths",
         f"{len(headings) - len(unused)} of {len(headings)}")
    examples(unused)

    # 10. Tokens saved by the space cleanup (raw text vs chunk source).
    raw = load_cached_document(path)
    before = sum(tok.count_tokens(normalize_text(i.text)) for i, _ in raw.iterate_items()
                 if getattr(i, "text", None))
    after = sum(tok.count_tokens(i.text) for i, _ in doc.iterate_items()
                if getattr(i, "text", None))
    line("INFO", "body text tokens", f"{before} before cleanup -> {after} after "
         f"({100 * (before - after) // max(before, 1)}% fewer)")

    deepest = max(parsed.chunk_candidates,
                  key=lambda c: len(c.headings), default=None)
    if deepest:
        line("INFO", "deepest heading path", " > ".join(
            h[:35] for h in deepest.headings))


def main():
    paths = sys.argv[1:] or DEFAULT_PATHS
    parser = DoclingParser()
    for p in paths:
        run(p, parser)


if __name__ == "__main__":
    main()
