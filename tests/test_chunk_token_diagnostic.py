import copy
import os
import sys

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from services.ingestion.normalization.text_normalizer import normalize_text
from tests.fixtures.docling_cache import load_cached_document


MAX_TOKENS = 512


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


def run(path: str):
    print("\n" + "=" * 80)
    print(os.path.basename(path))
    print("=" * 80)

    doc = normalize_docling_document(
        load_cached_document(path)
    )

    tokenizer = AutoTokenizer.from_pretrained(
        "google/gemma-2-9b-it"
    )

    chunk_tokenizer = HuggingFaceTokenizer(
        tokenizer=tokenizer,
        max_tokens=MAX_TOKENS,
    )

    chunker = HybridChunker(
        tokenizer=chunk_tokenizer,
        repeat_table_header=True,
        merge_peers=True,
        always_emit_headings=False,
    )

    chunks = list(chunker.chunk(doc))

    results = []

    for index, chunk in enumerate(chunks):
        try:
            text = chunker.contextualize(chunk).strip()
        except Exception:
            text = getattr(chunk, "text", "").strip()

        if not text:
            continue

        tokens = tokenizer(
            text,
            add_special_tokens=True,
            truncation=False,
            return_attention_mask=False,
        )["input_ids"]

        results.append(
            (
                index,
                len(text),
                len(tokens),
                " ".join(text.split())[:180],
            )
        )

    results.sort(key=lambda item: item[2], reverse=True)

    print(f"Total chunks: {len(results)}")
    print(f"Configured max_tokens: {MAX_TOKENS}")
    print()
    print("Largest chunks by tokenizer length:")
    print("-" * 80)

    for index, chars, tokens, preview in results[:15]:
        status = "OVER" if tokens > MAX_TOKENS else "OK"

        print(
            f"[{index:>3}] "
            f"chars={chars:>4} "
            f"tokens={tokens:>4} "
            f"{status:<4} "
            f"{preview}"
        )


def main():
    paths = sys.argv[1:]

    if not paths:
        raise SystemExit(
            "Usage: python tests/test_chunk_token_diagnostic.py <cache> ..."
        )

    for path in paths:
        run(path)


if __name__ == "__main__":
    main()
