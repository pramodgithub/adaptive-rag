import copy
import os
import re
import statistics
import sys

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from services.ingestion.normalization.text_normalizer import normalize_text
from tests.fixtures.docling_cache import load_cached_document


ORPHAN_MIN_CHARS = 150
MAX_TOKENS = 700

BIDI_CHARS = {
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}

TARGET_PATTERNS = [
    r"Article\s+32",
    r"CC6\.1\.4",
    r"CC6\.1\.5",
    r"CC6\.1\.6",
]


def normalize_docling_document(doc):
    normalized = copy.deepcopy(doc)

    for item in getattr(normalized, "texts", []):
        text = getattr(item, "text", None)
        if text:
            item.text = normalize_text(text)

    for table in getattr(normalized, "tables", []):
        data = getattr(table, "data", None)

        if data is None:
            continue

        for cell in getattr(data, "table_cells", []):
            text = getattr(cell, "text", None)
            if text:
                cell.text = normalize_text(text)

    return normalized


def count_bidi(text: str) -> int:
    return sum(char in BIDI_CHARS for char in text)


def document_bidi_count(doc) -> int:
    total = 0

    for item in getattr(doc, "texts", []):
        total += count_bidi(getattr(item, "text", ""))

    for table in getattr(doc, "tables", []):
        data = getattr(table, "data", None)

        if data is None:
            continue

        for cell in getattr(data, "table_cells", []):
            total += count_bidi(getattr(cell, "text", ""))

    return total


def chunk_texts(chunker, chunks):
    texts = []

    for chunk in chunks:
        try:
            text = chunker.contextualize(chunk)
        except Exception:
            text = getattr(chunk, "text", "")

        if text and text.strip():
            texts.append(text.strip())

    return texts


def merge_orphans(
    texts: list[str],
    min_chars: int = ORPHAN_MIN_CHARS,
) -> list[str]:
    merged = []
    carry = None

    for text in texts:
        if carry is not None:
            text = carry + "\n" + text
            carry = None

        if len(text) < min_chars:
            carry = text
            continue

        merged.append(text)

    if carry is not None:
        if merged:
            merged[-1] += "\n" + carry
        else:
            merged.append(carry)

    return merged


def chunk_stats(texts: list[str]) -> dict:
    sizes = [len(text) for text in texts if text.strip()]

    if not sizes:
        return {
            "chunks": 0,
            "avg": 0,
            "median": 0,
            "min": 0,
            "max": 0,
            "short": 0,
            "large": 0,
        }

    return {
        "chunks": len(sizes),
        "avg": round(statistics.mean(sizes)),
        "median": round(statistics.median(sizes)),
        "min": min(sizes),
        "max": max(sizes),
        "short": sum(size < ORPHAN_MIN_CHARS for size in sizes),
        "large": sum(size > 3200 for size in sizes),
    }


def print_stats(label: str, stats: dict):
    print(
        f"{label:<22} "
        f"chunks={stats['chunks']:<4} "
        f"avg={stats['avg']:<5} "
        f"median={stats['median']:<5} "
        f"min={stats['min']:<4} "
        f"max={stats['max']:<5} "
        f"short={stats['short']:<3} "
        f">3200={stats['large']}"
    )


def find_targets(texts: list[str]) -> dict:
    results = {}

    for pattern in TARGET_PATTERNS:
        matches = [
            index
            for index, text in enumerate(texts)
            if re.search(pattern, text, re.IGNORECASE)
        ]

        results[pattern] = matches

    return results


def print_target_summary(label: str, texts: list[str]):
    print(f"\n{label}")

    results = find_targets(texts)

    for pattern, matches in results.items():
        if matches:
            print(f"  {pattern:<12} FOUND in chunks {matches[:8]}")
        else:
            print(f"  {pattern:<12} NOT FOUND")


def print_selected_samples(texts: list[str], indexes: list[int]):
    for index in indexes:
        if index >= len(texts):
            continue

        text = texts[index]
        preview = re.sub(r"\s+", " ", text)

        if len(preview) > 300:
            preview = preview[:300] + "..."

        print(f"  [{index}] {len(text)} chars: {preview}")


def run_document(cache_path: str):
    print("\n" + "=" * 80)
    print(f"DOCUMENT: {os.path.basename(cache_path)}")
    print("=" * 80)

    doc = load_cached_document(cache_path)

    raw_bidi = document_bidi_count(doc)
    normalized_doc = normalize_docling_document(doc)
    normalized_bidi = document_bidi_count(normalized_doc)

    tokenizer = HuggingFaceTokenizer(
        tokenizer=AutoTokenizer.from_pretrained(
            "google/gemma-2-9b-it"
        ),
        max_tokens=MAX_TOKENS,
    )

    chunker = HybridChunker(
        tokenizer=tokenizer,
        repeat_table_header=True,
        merge_peers=True,
        always_emit_headings=False,
    )

    raw_chunks = list(chunker.chunk(doc))
    normalized_chunks = list(chunker.chunk(normalized_doc))

    raw_texts = chunk_texts(chunker, raw_chunks)
    normalized_texts = chunk_texts(chunker, normalized_chunks)

    raw_merged = merge_orphans(raw_texts)
    normalized_merged = merge_orphans(normalized_texts)

    raw_stats = chunk_stats(raw_texts)
    normalized_stats = chunk_stats(normalized_texts)
    raw_merged_stats = chunk_stats(raw_merged)
    normalized_merged_stats = chunk_stats(normalized_merged)

    print("\nDOCUMENT")
    print(f"  Elements:             {len(getattr(doc, 'texts', []))}")
    print(f"  Tables:               {len(getattr(doc, 'tables', []))}")

    print("\nNORMALIZATION")
    print(f"  Bidi before:          {raw_bidi}")
    print(f"  Bidi after:           {normalized_bidi}")
    print(f"  Bidi removed:         {raw_bidi - normalized_bidi}")

    print("\nRAW HYBRID")
    print_stats("Raw", raw_stats)

    print("\nNORMALIZED HYBRID")
    print_stats("Normalized", normalized_stats)

    print("\nORPHAN MERGE")
    print_stats("Raw merged", raw_merged_stats)
    print_stats("Normalized merged", normalized_merged_stats)

    print_target_summary(
        "TARGETS — NORMALIZED RAW",
        normalized_texts,
    )

    print_target_summary(
        "TARGETS — NORMALIZED MERGED",
        normalized_merged,
    )

    short_indexes = [
        index
        for index, text in enumerate(normalized_texts)
        if len(text) < ORPHAN_MIN_CHARS
    ]

    print("\nREMAINING SHORT CHUNKS")
    if not short_indexes:
        print("  None")
    else:
        print(f"  Count: {len(short_indexes)}")
        print_selected_samples(normalized_texts, short_indexes[:10])

    print("\nFINAL DECISION")

    checks = {
        "bidi cleaned": normalized_bidi == 0,
        "orphan merge effective": normalized_merged_stats["short"] == 0,
        "targets preserved": all(
            find_targets(normalized_merged).values()
        ),
    }

    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'REVIEW'}] {name}")

    if all(checks.values()):
        print("\n  RESULT: PASS — proceed to the next ingestion step.")
    else:
        print("\n  RESULT: REVIEW — investigate the failed check before proceeding.")


def main():
    paths = sys.argv[1:]

    if not paths:
        print(
            "Usage:\n"
            "  python tests/test_cached_chunking_final.py "
            "<cache> [<cache> ...]"
        )
        raise SystemExit(1)

    for path in paths:
        if not os.path.exists(path):
            print(f"ERROR: cache does not exist: {path}")
            continue

        run_document(path)


if __name__ == "__main__":
    main()
