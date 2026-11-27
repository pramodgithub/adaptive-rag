#!/usr/bin/env python
"""Robust cached Docling ingestion runner.

Usage:
  docker compose exec -T worker python tests/ingest_cached_documents.py \
    tests/data/cache/SOC2.docling.json \
    tests/data/cache/CELEX_32016R0679_EN_TXT.docling.json \
    --outdir out/ingestion
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass, field

from tests.fixtures.docling_cache import load_cached_document

from services.ingestion.semantics.extractor import SemanticEntityExtractor
from services.ingestion.semantics.heading_labels import attach_heading_labels
from services.ingestion.semantics.postprocess import postprocess_entities


# --------------------------------------------------------------------- models

@dataclass
class GenericChunk:
    chunk_index: int
    text: str
    metadata: dict = field(default_factory=dict)


# --------------------------------------------------------------------- helpers

def _etype_name(value) -> str:
    if value is None:
        return "unknown"
    return str(getattr(value, "name", value)).lower()


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]

    if hasattr(value, "name") and not isinstance(value, str):
        return value.name.lower()

    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return value.value

    return value


def entity_to_dict(obj) -> dict:
    if hasattr(obj, "model_dump"):
        try:
            d = obj.model_dump()
        except Exception:
            d = obj.dict()
    elif hasattr(obj, "dict") and callable(obj.dict):
        d = obj.dict()
    elif hasattr(obj, "__dict__"):
        d = dict(obj.__dict__)
    else:
        d = dict(obj)

    return _jsonable(d)


def infer_framework(path: str) -> str:
    name = os.path.basename(path).lower()

    if "celex" in name or "2016r0679" in name or "gdpr" in name:
        return "gdpr"

    if "soc2" in name:
        return "soc2"

    return "unknown"


# --------------------------------------------------------------- element utils

def _item_text(el) -> str:
    for attr in ("text", "orig", "content", "value"):
        v = getattr(el, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _attr_str(el, name: str) -> str:
    v = getattr(el, name, None)
    if v is None:
        return ""
    v = getattr(v, "value", v)
    return str(v).lower()


def _is_headingish(el) -> bool:
    """Very generic heading detector.

    Works with objects exposing element_type / label / kind / role.
    """
    for name in ("element_type", "label", "kind", "role"):
        s = _attr_str(el, name)
        if not s:
            continue

        if any(k in s for k in ("heading", "header", "title", "chapter", "section")):
            return True

    return False


def _document_elements(doc) -> list:
    """Try to get a usable element list from a Docling document."""
    for source in (
        getattr(doc, "elements", None),
        getattr(doc, "texts", None),
    ):
        if source is None:
            continue

        try:
            items = list(source)
            if items:
                return items
        except TypeError:
            continue

    return []


def _looks_title_like(text: str, max_chars: int = 500, max_words: int = 80) -> bool:
    s = str(text or "").strip()
    if not s:
        return False

    if len(s) > max_chars:
        return False

    if len(s.split()) > max_words:
        return False

    if s[-1] in ".;:!?":
        return False

    return True


# ------------------------------------------------------------- heading recovery

def _find_label_title_pairs(doc, extractor: SemanticEntityExtractor) -> list[tuple[str, str]]:
    """Fallback pair finder.

    Does not rely on element_type being exactly 'heading'. It only requires:
      - first element text is a bare identifier
      - second element text looks like a title
    """
    elements = _document_elements(doc)

    texts: list[str] = []
    for el in elements:
        txt = _item_text(el)
        if txt:
            texts.append(txt)

    pairs: list[tuple[str, str]] = []

    for first, second in zip(texts, texts[1:]):
        first = first.strip()
        second = second.strip()

        if not first or not second:
            continue

        if len(first) > 80:
            continue

        if not _looks_title_like(second):
            continue

        try:
            if extractor.is_bare_identifier(first) and not extractor.is_bare_identifier(second):
                pairs.append((first, second))
        except Exception:
            continue

    return pairs


def _attach_pairs_to_chunks(
    chunks: list[GenericChunk],
    pairs: list[tuple[str, str]],
    separator: str = " – ",
) -> int:
    changed = 0
    cursor = 0
    current: tuple[str, str] | None = None

    for chunk in chunks:
        headings = chunk.metadata.get("headings") or []
        if not headings:
            continue

        last = str(headings[-1]).strip()
        pair = None

        if current and current[1] == last:
            pair = current
        else:
            for k in range(cursor, min(len(pairs), cursor + 10)):
                if pairs[k][1] == last:
                    current, cursor, pair = pairs[k], k + 1, pairs[k]
                    break

        if pair is None:
            continue

        label, title = pair
        headings = list(headings)
        headings[-1] = f"{label}{separator}{title}"

        chunk.metadata["headings"] = headings
        chunk.metadata["heading_label"] = label
        changed += 1

    return changed


def attach_heading_labels_robust(
    doc,
    chunks: list[GenericChunk],
    extractor: SemanticEntityExtractor,
) -> int:
    """Try the original attach_heading_labels first, then a generic fallback."""

    # Try likely element sources accepted by the original function.
    sources = []

    if getattr(doc, "elements", None) is not None:
        sources.append(("doc.elements", doc.elements))

    if getattr(doc, "texts", None) is not None:
        sources.append(("doc.texts", doc.texts))

    sources.append(("doc", doc))

    for name, source in sources:
        try:
            changed = attach_heading_labels(source, chunks, extractor)
            if changed:
                print(
                    f"[diag] attach_heading_labels via {name} changed {changed} chunk(s)")
                return changed
        except Exception as exc:
            print(f"[diag] attach_heading_labels via {name} failed: {exc}")

    # Fallback: find pairs directly from document text elements.
    pairs = _find_label_title_pairs(doc, extractor)
    changed = _attach_pairs_to_chunks(chunks, pairs)

    print(
        f"[diag] fallback heading pairs found={len(pairs)} changed={changed}")
    return changed


# ------------------------------------------------------------------- chunking

def _headings_from_meta(meta) -> list[str]:
    headings: list[str] = []

    for item in getattr(meta, "doc_items", []) or []:
        if _is_headingish(item):
            txt = _item_text(item)
            if txt:
                headings.append(txt)

    return headings


def _build_chunks(
    doc,
    max_tokens: int,
    always_emit_headings: bool,
) -> list[GenericChunk]:
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
    from transformers import AutoTokenizer

    tokenizer = HuggingFaceTokenizer(
        tokenizer=AutoTokenizer.from_pretrained("google/gemma-2-9b-it"),
        max_tokens=max_tokens,
    )

    common = dict(
        tokenizer=tokenizer,
        repeat_table_header=True,
        merge_peers=True,
    )

    try:
        chunker = HybridChunker(
            always_emit_headings=always_emit_headings, **common)
    except TypeError:
        # Older/newer versions may not accept this parameter.
        chunker = HybridChunker(**common)

    chunks: list[GenericChunk] = []

    for i, ch in enumerate(chunker.chunk(doc)):
        text = chunker.contextualize(ch) or getattr(ch, "text", "") or ""
        meta = getattr(ch, "meta", None)

        headings = [
            str(h)
            for h in (getattr(meta, "headings", []) or [])
            if str(h).strip()
        ]

        if not headings:
            headings = _headings_from_meta(meta)

        chunks.append(
            GenericChunk(
                chunk_index=i,
                text=text,
                metadata={"headings": headings},
            )
        )

    return chunks


# ---------------------------------------------------------------- diagnostics

def print_chunk_diag(chunks: list[GenericChunk], limit: int = 5) -> None:
    shown = 0

    for c in chunks:
        interesting = (
            c.metadata.get("headings")
            or "CC" in c.text
            or "Article" in c.text
            or "Chapter" in c.text
            or "Section" in c.text
        )

        if not interesting:
            continue

        text = c.text.replace("\n", " | ")
        print(f"[chunk {c.chunk_index}] headings={c.metadata.get('headings')}")
        print(f"  text: {text[:220]}")

        shown += 1
        if shown >= limit:
            break


def print_raw_summary(raw_entities) -> None:
    kinds = Counter()
    types = Counter()

    for e in raw_entities:
        md = getattr(e, "metadata", None) or {}
        kinds[md.get("candidate_kind", "unknown")] += 1
        types[_etype_name(getattr(e, "entity_type", None))] += 1

    print(f"[diag] raw entities: {len(raw_entities)}")
    print(f"[diag] raw candidate_kind: {dict(kinds)}")
    print(f"[diag] raw entity_type: {dict(types)}")


def print_marker_counts(chunks: list[GenericChunk]) -> None:
    markers = ["CC", "Article", "Chapter", "Section", "Annex", "Appendix"]

    counts = {}
    for marker in markers:
        needle = marker.lower()
        counts[marker] = sum(1 for c in chunks if needle in c.text.lower())

    print(f"[diag] chunk marker counts: {counts}")


# --------------------------------------------------------------------- report

def print_report(
    source: str,
    chunk_count: int,
    relabel_count: int,
    raw_count: int,
    entities: list[dict],
    mentions: list[dict],
    stats: dict,
) -> None:
    print("\n" + "=" * 80)
    print(f"INGESTION REPORT  {os.path.basename(source)}")
    print("=" * 80)

    print(f"chunks: {chunk_count}")
    print(f"label-only headings re-attached: {relabel_count}")
    print(f"raw entities before postprocess: {raw_count}")

    print(
        f"primary entities: {len(entities)} "
        f"(definitions {stats['definitions']}, inferred {stats['inferred']})"
    )

    print(
        f"mentions / reference-only: {len(mentions)} "
        f"(noise dropped {stats['noise_references']})"
    )

    print(f"by type: {stats['by_type']}")
    print(f"title coverage: {stats['with_title']}/{stats['definitions']}")
    print(
        f"description coverage: {stats['with_description']}/{stats['definitions']}")
    print(f"neither title nor description: {stats['neither']}")
    print(
        f"parents resolved by key: {stats['parents_resolved']}/{len(entities)}")

    if stats["gaps"]:
        print("\nRemaining gaps:")
        for g in stats["gaps"][:20]:
            print(f"  {g}")


# ------------------------------------------------------------------------ run

def run(
    path: str,
    outdir: str | None,
    framework: str | None,
    max_tokens: int,
    keep_reference: bool,
    save_chunks: bool,
    debug: bool,
) -> None:
    doc = load_cached_document(path)
    extractor = SemanticEntityExtractor()

    # First try the less noisy chunking mode.
    chunks = _build_chunks(doc, max_tokens=max_tokens,
                           always_emit_headings=False)
    with_headings = sum(1 for c in chunks if c.metadata.get("headings"))

    # If no headings survived, retry with always_emit_headings=True.
    if with_headings == 0:
        print(
            "[diag] no chunk headings with always_emit_headings=False; retrying with True")
        chunks = _build_chunks(doc, max_tokens=max_tokens,
                               always_emit_headings=True)
        with_headings = sum(1 for c in chunks if c.metadata.get("headings"))

    print(f"[diag] chunks={len(chunks)} with_headings={with_headings}")
    print_marker_counts(chunks)

    if debug:
        print_chunk_diag(chunks)

    relabel_count = attach_heading_labels_robust(doc, chunks, extractor)

    raw_entities = extractor.extract_document(
        chunks,
        framework=framework or infer_framework(path),
    )

    print_raw_summary(raw_entities)

    if not raw_entities:
        print(
            "[warn] extractor returned 0 raw entities. "
            "The problem is before post-processing: chunk text/headings are wrong "
            "or the extractor profile does not match this document."
        )

    entity_dicts = [entity_to_dict(e) for e in raw_entities]

    entities, mentions, stats = postprocess_entities(
        entity_dicts,
        chunks,
        extractor=extractor,
        keep_reference=keep_reference,
    )

    payload = {
        "source": path,
        "framework": framework or infer_framework(path),
        "chunk_count": len(chunks),
        "heading_labels_reattached": relabel_count,
        "raw_entity_count": len(raw_entities),
        "entities": entities,
        "mentions": mentions,
        "stats": stats,
    }

    if save_chunks:
        payload["chunks"] = [
            {
                "chunk_index": c.chunk_index,
                "headings": c.metadata.get("headings", []),
                "text": c.text,
            }
            for c in chunks
        ]

    if outdir:
        os.makedirs(outdir, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0]
        outpath = os.path.join(outdir, f"{base}.ingestion.json")

        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"wrote {outpath}")

    print_report(
        source=path,
        chunk_count=len(chunks),
        relabel_count=relabel_count,
        raw_count=len(raw_entities),
        entities=entities,
        mentions=mentions,
        stats=stats,
    )


# ----------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--framework", default=None)
    ap.add_argument("--outdir", default="out/ingestion")
    ap.add_argument("--max-tokens", type=int, default=700)
    ap.add_argument(
        "--keep-reference",
        action="store_true",
        help="Keep non-noise reference-only entities in primary entities.",
    )
    ap.add_argument(
        "--save-chunks",
        action="store_true",
        help="Also save chunk text/headings into the output JSON.",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Print sample chunk diagnostics.",
    )

    args = ap.parse_args()

    for p in args.paths:
        if not os.path.exists(p):
            print(f"ERROR: missing {p}")
            continue

        run(
            path=p,
            outdir=args.outdir,
            framework=args.framework,
            max_tokens=args.max_tokens,
            keep_reference=args.keep_reference,
            save_chunks=args.save_chunks,
            debug=args.debug,
        )


if __name__ == "__main__":
    main()
