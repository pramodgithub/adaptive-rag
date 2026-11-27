# tests/test_identifier_detection.py
import re
import sys
from collections import Counter
from tests.fixtures.docling_cache import load_cached_document
from services.ingestion.normalization.text_normalizer import normalize_text

ID_RX = re.compile(r"""^\s*(?P<id>
    (?:Art(?:icle)?\.?\s*\d+(?:\(\d+\))?)               # Article 32, Art. 5(1)
  | (?:[A-Za-z]{1,4}[-.]?\d+(?:[.\-]\d+)+(?:\(\d+\))?)  # CC6.1.4, A1.2, A.9.4.1
  | (?:[A-Za-z]{1,4}-\d+(?:\(\d+\))?)                   # AC-2, AC-2(1)
  | (?:\d+(?:\.\d+){1,5})                               # 4.2.1
)(?=[\s:.\-–—)]|$)""", re.X)

DATE_RX = re.compile(r"^\s*\d{1,2}[./]\d{1,2}[./](?:19|20)\d{2}\b")


def ident(text):
    t = normalize_text(text or "")
    if DATE_RX.match(t):
        return None
    m = ID_RX.match(t)
    return m.group("id").upper() if m else None


def is_body(item):
    return "BODY" in str(getattr(item, "content_layer", "BODY"))


for path in sys.argv[1:]:
    doc = load_cached_document(path)
    print("\n" + "=" * 70, "\n", path)

    print("\nTABLES: rows without an identifier (excluding row 0)")
    for ti, t in enumerate(doc.tables):
        first = {}
        for c in t.data.table_cells:
            if c.start_col_offset_idx == 0:
                first[c.start_row_offset_idx] = c.text
        ids = [ident(first.get(r, "")) for r in range(t.data.num_rows)]
        if sum(i is not None for i in ids) < 3:
            continue  # not a control-style table
        for r, i in enumerate(ids):
            if i is None and r > 0:
                row = sorted(
                    (c for c in t.data.table_cells
                     if c.start_row_offset_idx <= r < c.end_row_offset_idx),
                    key=lambda c: c.start_col_offset_idx)
                print(f"  table {ti} row {r}: " +
                      " | ".join(normalize_text(c.text)[:50] for c in row))

    print("\nBODY TEXT ITEMS (len <= 60)")
    found, samples = Counter(), {}
    for t in doc.texts:
        if not is_body(t):
            continue
        txt = normalize_text(t.text or "")
        if len(txt) <= 60 and (i := ident(txt)):
            lab = str(t.label)
            found[lab] += 1
            samples.setdefault(lab, []).append((i, txt))
    print("  by label:", dict(found))
    for lab, items in samples.items():
        print(f"  {lab}:")
        for i, txt in items[:15]:
            print(f"     {i!r:<14} <- {txt!r}")
