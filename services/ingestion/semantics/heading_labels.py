"""Re-attach label-only headings ("Article 6") to the heading that follows them.

Many documents emit the structural label and its title as two consecutive
headings:

    heading  "Article 6"
    heading  "Lawfulness of processing"

Chunk builders usually keep only the last heading, so the label never reaches
the chunk and entity extraction cannot see it. This pass reads the parsed
elements (where both headings still exist) and writes the combined heading
back into ``chunk.metadata["headings"]``. Chunk text and indices are untouched.

Nothing here is framework specific: "label-only" is decided by the extractor's
own identifier grammar.
"""
from __future__ import annotations

from typing import Iterable

from services.ingestion.semantics.extractor import SemanticEntityExtractor

_LOOKAHEAD_PAIRS = 5


def _is_heading(element) -> bool:
    kind = getattr(element, "element_type", None)
    return str(getattr(kind, "value", kind)).lower() == "heading"


def label_heading_pairs(
    elements: Iterable, extractor: SemanticEntityExtractor
) -> list[tuple[str, str]]:
    """(label, title) for every label-only heading followed directly by a heading."""
    items = list(elements)
    pairs: list[tuple[str, str]] = []
    for first, second in zip(items, items[1:]):
        if not (_is_heading(first) and _is_heading(second)):
            continue
        label = (getattr(first, "text", "") or "").strip()
        title = (getattr(second, "text", "") or "").strip()
        if (
            label and title
            and extractor.is_bare_identifier(label)
            and not extractor.is_bare_identifier(title)
        ):
            pairs.append((label, title))
    return pairs


def attach_heading_labels(
    document_or_elements,
    chunks: Iterable,
    extractor: SemanticEntityExtractor | None = None,
    separator: str = " – ",
) -> int:
    """Rewrite chunk.metadata['headings'][-1] to 'Label – Title'. Returns chunks changed."""
    extractor = extractor or SemanticEntityExtractor()
    elements = getattr(document_or_elements, "elements", document_or_elements)
    pairs = label_heading_pairs(elements, extractor)

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
            pair = current  # continuation chunk of the same section
        else:
            for k in range(cursor, min(len(pairs), cursor + _LOOKAHEAD_PAIRS)):
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
