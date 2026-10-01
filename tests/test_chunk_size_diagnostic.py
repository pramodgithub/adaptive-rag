import os
import sys

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from services.ingestion.normalization.text_normalizer import normalize_text
from tests.fixtures.docling_cache import load_cached_document

import copy


MAX_TOKENS = 700
LARGE_CHUNK_CHARS = 3200


def normalize_docling_document(doc):
    normalized = copy.deepcopy(doc)

    for item in getattr(normalized, "texts", []):
        if getattr(item, "text", None):
            item.text = normalize_text(item.text)

    for table in getattr(normalized, "tables", []):
        data = getattr(table, "data", None)

        if data is None:
            continue

        for cell in getattr(data, "table_cells", []):
            if getattr(cell, "text", None):
                cell.text = normalize_text(cell.text)

    return normalized


def build_chunker():
    tokenizer = HuggingFaceTokenizer(
        tokenizer=AutoTokenizer.from_pretrained(
            "google/gemma-2-9b-it"
        ),
        max_tokens=MAX_TOKENS,
    )

    return HybridChunker(
        tokenizer=tokenizer,
        repeat_table_header=True,
        merge_peers=True,
        always_emit_headings=False,
    )


def get_text(chunker, chunk):
    try:
        return chunker.contextualize(chunk).strip()
    except Exception:
        return getattr(chunk, "text", "").strip()


def run(path):
    print("\n" + "=" * 80)
    print(os.path.basename(path))
    print("=" * 80)

    doc = load_cached_document(path)
    normalized = normalize_docling_document(doc)

    chunker = build_chunker()
    chunks = list(chunker.chunk(normalized))

    large = []

    for index, chunk in enumerate(chunks):
        text = get_text(chunker, chunk)

        if len(text) > LARGE_CHUNK_CHARS:
            large.append((index, text))

    print(f"Total chunks:       {len(chunks)}")
    print(f"Large chunks:       {len(large)}")
    print(f"Threshold:          {LARGE_CHUNK_CHARS} chars")

    for index, text in large:
        preview = " ".join(text.split())

        print(
            f"\n[{index}] {len(text)} chars"
            f"\n{preview[:500]}"
        )


def main():
    paths = sys.argv[1:]

    if not paths:
        raise SystemExit(
            "Usage: python tests/test_chunk_size_diagnostic.py <cache> ..."
        )

    for path in paths:
        run(path)


if __name__ == "__main__":
    main()
