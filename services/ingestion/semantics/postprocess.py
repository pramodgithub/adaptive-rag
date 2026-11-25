"""Generic post-processing for deterministic entity extraction.

This module is intentionally framework-agnostic.

It operates on plain dict entities so it can be used with pydantic,
dataclass, or ORM objects after conversion.

Responsibilities:
- normalize identifiers
- merge duplicate entities
- infer missing intermediate dotted parents
- fill missing titles/descriptions using generic chunk lookahead
- split reference-only mentions from primary entities
- resolve parents using:
  1. dotted identifier hierarchy
  2. heading path / labelled containment
  3. document-order containment fallback
"""

from __future__ import annotations

import re
from collections import defaultdict


# --------------------------------------------------------------------- regex

CODE_CANON_RE = re.compile(
    r"^(?P<scheme>[A-Za-z]{1,10})[.\-_ ]?(?P<nums>\d+(?:[.\-_]\d+)*)$"
)
PURE_NUM_RE = re.compile(r"^\d+(?:[./-]\d+)*$")
ROMAN_RE = re.compile(r"^[IVXLCDM]+$", re.I)
SENTENCE_END_RE = re.compile(r"[.;:!?]$")
NOISE_CHARS = " \t-–—•#>*|"

DEFAULT_RANK = {
    "part": 0,
    "chapter": 1,
    "annex": 1,
    "appendix": 1,
    "schedule": 1,
    "section": 2,
    "article": 3,
}


# --------------------------------------------------------------- small utils

def _etype_name(value) -> str:
    if value is None:
        return "unknown"
    return str(getattr(value, "name", value)).lower()


def _norm_id(value) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _truncate_words(text: str | None, words: int = 14, chars: int = 160) -> str | None:
    text = str(text or "").strip()
    if not text:
        return None
    parts = text.split()
    if len(parts) > words:
        text = " ".join(parts[:words]) + "…"
    if len(text) > chars:
        text = text[: chars - 1].rstrip() + "…"
    return text


def _chunk_index(chunk) -> int | None:
    return getattr(chunk, "chunk_index", None)


def _chunk_text(chunk) -> str:
    return getattr(chunk, "text", "") or ""


def _chunk_headings(chunk) -> list[str]:
    md = getattr(chunk, "metadata", None) or {}
    return [str(h) for h in (md.get("headings", []) or [])]


def normalize_code_identifier(identifier: str) -> str:
    """Normalize code-like identifiers.

    Examples:
      CC-1.1    -> CC1.1
      A.1.1     -> A1.1
      ISO-27001 -> ISO27001
    """
    s = re.sub(r"\s+", "", str(identifier or "")).strip()
    m = CODE_CANON_RE.match(s)
    if not m:
        return s

    nums = [n for n in re.split(r"[.\-_]", m.group("nums")) if n]
    if not nums:
        return s

    canon = f"{m.group('scheme').upper()}{nums[0]}"
    if len(nums) > 1:
        canon += "." + ".".join(nums[1:])
    return canon


def entity_key(entity: dict) -> str:
    md = entity.get("metadata") or {}
    key = md.get("entity_key")
    if key:
        return str(key)
    kind = md.get("candidate_kind") or _etype_name(
        entity.get("entity_type")) or "entity"
    return f"{kind}:{_norm_id(entity.get('identifier'))}"


def _structural_kind(entity: dict) -> str:
    md = entity.get("metadata") or {}
    key = str(md.get("entity_key") or "")
    if ":" in key:
        return key.split(":", 1)[0]
    return _etype_name(entity.get("entity_type"))


def qualified_name(entity: dict) -> str:
    md = entity.get("metadata") or {}
    label = str(md.get("label") or "").strip().capitalize()
    ident = str(entity.get("identifier") or "").strip()
    base = f"{label} {ident}" if label else ident
    title = entity.get("title")
    return f"{base} – {title}" if title else base


def _identifier_regex(entity: dict) -> re.Pattern | None:
    md = entity.get("metadata") or {}
    vals = {str(entity.get("identifier") or "")}
    vals.update(str(x) for x in md.get("identifier_aliases", []) or [])
    if md.get("original_identifier"):
        vals.add(str(md["original_identifier"]))
    vals = {v for v in vals if v}
    if not vals:
        return None

    pattern = "|".join(re.escape(v)
                       for v in sorted(vals, key=len, reverse=True))
    return re.compile(
        r"(?<![A-Za-z0-9])(?:" + pattern + r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def _match_entity_in_text(entity: dict, text: str) -> bool:
    rx = _identifier_regex(entity)
    return bool(rx and rx.search(str(text or "")))


# ---------------------------------------------------------------- normalize

def normalize_identifiers(entities: list[dict]) -> list[dict]:
    for e in entities:
        md = e.setdefault("metadata", {})
        ident = str(e.get("identifier", "")).strip()
        is_code = (
            _structural_kind(e) == "code"
            or md.get("scheme")
            or _etype_name(e.get("entity_type")) == "code"
        )

        aliases = {ident}
        if is_code and ident:
            canon = normalize_code_identifier(ident)
            if canon and canon != ident:
                md["original_identifier"] = ident
                e["identifier"] = canon
                ident = canon
            md["entity_key"] = f"code:{_norm_id(ident)}"
            aliases.add(canon)

        md["identifier_aliases"] = sorted({a for a in aliases if a})
    return entities


# ------------------------------------------------------------------- merging

def _merge_score(entity: dict):
    md = entity.get("metadata") or {}
    return (
        1 if md.get("candidate_kind") in ("definition", "inferred") else 0,
        float(entity.get("confidence") or 0),
        bool(entity.get("title")),
        bool(md.get("description")),
    )


def merge_duplicate_entities(entities: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in entities:
        groups[entity_key(e)].append(e)

    out: list[dict] = []
    for key, items in groups.items():
        if len(items) == 1:
            items[0].setdefault("metadata", {})["entity_key"] = key
            out.append(items[0])
            continue

        best = max(items, key=_merge_score)
        merged = dict(best)
        md = dict(best.get("metadata") or {})
        merged["metadata"] = md
        md["entity_key"] = key

        def_chunks = sorted({
            c
            for it in items
            for c in ((it.get("metadata") or {}).get("definition_chunks") or [])
        })
        ref_chunks = sorted({
            c
            for it in items
            for c in ((it.get("metadata") or {}).get("reference_chunks") or [])
        })

        if def_chunks:
            md["definition_chunks"] = def_chunks
        if ref_chunks:
            md["reference_chunks"] = ref_chunks[:50]

        md["reference_count"] = sum(
            int((it.get("metadata") or {}).get("reference_count") or 0)
            for it in items
        )

        if not merged.get("title"):
            merged["title"] = next(
                (
                    it.get("title")
                    for it in sorted(items, key=_merge_score, reverse=True)
                    if it.get("title")
                ),
                None,
            )

        if not md.get("description"):
            md["description"] = next(
                (
                    (it.get("metadata") or {}).get("description")
                    for it in sorted(items, key=_merge_score, reverse=True)
                    if (it.get("metadata") or {}).get("description")
                ),
                None,
            )

        md["merged_from"] = sorted({
            str((it.get("metadata") or {}).get("entity_key") or entity_key(it))
            for it in items
        })

        merged["confidence"] = max(
            float(it.get("confidence") or 0) for it in items)
        out.append(merged)

    return out


# ------------------------------------------------------- inferred placeholders

def infer_missing_intermediate_entities(entities: list[dict], max_levels: int = 3) -> list[dict]:
    """Infer missing intermediate dotted parents.

    Example:
      A1.1.1 exists but A1.1 does not -> create placeholder A1.1.
    """
    existing = {entity_key(e) for e in entities}
    ids = {_norm_id(e.get("identifier")) for e in entities}
    extra: list[dict] = []

    for e in entities:
        md = e.get("metadata") or {}
        if md.get("candidate_kind") not in ("definition", None):
            continue

        ident = str(e.get("identifier") or "")
        if "." not in ident:
            continue

        current = ident
        for _ in range(max_levels):
            if "." not in current:
                break

            parent = current.rsplit(".", 1)[0]
            if "." not in parent:
                break

            candidates = [parent, parent + ".0",
                          normalize_code_identifier(parent)]
            if any(_norm_id(c) in ids for c in candidates):
                current = parent
                continue

            kind = _structural_kind(e) or "code"
            key = f"{kind}:{_norm_id(parent)}"
            if key not in existing:
                extra.append({
                    "framework": e.get("framework", "unknown"),
                    "identifier": parent,
                    "entity_type": e.get("entity_type"),
                    "title": None,
                    "parent_identifier": None,
                    "confidence": 0.25,
                    "validation_status": "inferred",
                    "source": "inferred",
                    "metadata": {
                        "entity_key": key,
                        "candidate_kind": "inferred",
                        "label": md.get("label"),
                        "scheme": md.get("scheme"),
                        "inferred_from_child": str(e.get("identifier")),
                        "definition_chunks": (md.get("definition_chunks") or [])[:1],
                    },
                })
                existing.add(key)
                ids.add(_norm_id(parent))

            current = parent

    return entities + extra


# ------------------------------------------------------------ title fallback

def _looks_like_title(line: str, max_chars: int = 500, max_words: int = 60) -> bool:
    s = str(line or "").strip(NOISE_CHARS)
    if not s or len(s) > max_chars:
        return False

    words = s.split()
    if len(words) > max_words:
        return False

    if SENTENCE_END_RE.search(s):
        return False

    if s[0].isdigit():
        return False

    if re.match(r"^(page|table|figure)\b", s, re.I):
        return False

    return True


def _collect_desc(lines: list[str], start: int, max_chars: int = 500) -> str | None:
    parts: list[str] = []
    total = 0

    for j in range(start, min(start + 12, len(lines))):
        s = lines[j].strip()
        if not s:
            if parts:
                break
            continue

        if _looks_like_title(s, max_chars=200, max_words=30):
            break

        parts.append(s)
        total += len(s)
        if total >= max_chars:
            break

    if not parts:
        return None

    return " ".join(parts)[:max_chars]


def _capture_description_for_entity(
    entity: dict,
    chunks_by_idx: dict[int, object],
    max_chars: int = 500,
) -> str | None:
    md = entity.get("metadata") or {}
    rx = _identifier_regex(entity)
    title = entity.get("title")

    def_chunks = (
        md.get("definition_chunks")
        or ([md["chunk_index"]] if md.get("chunk_index") is not None else [])
    )

    for ci in def_chunks[:2]:
        chunk = chunks_by_idx.get(ci)
        if not chunk:
            continue

        lines = _chunk_text(chunk).splitlines()
        start = None

        for i, line in enumerate(lines):
            if title and str(title).casefold() in line.casefold():
                start = i
                break
            if rx and rx.search(line):
                start = i
                break

        if start is None:
            continue

        return _collect_desc(lines, start + 1, max_chars)

    return None


def fill_titles_and_descriptions(
    entities: list[dict],
    chunks: list[object],
    max_desc_chars: int = 500,
) -> list[dict]:
    by_idx = {_chunk_index(c): c for c in chunks}

    for e in entities:
        md = e.setdefault("metadata", {})
        if md.get("candidate_kind") == "reference":
            continue

        desc = md.get("description")

        # 1) If we have description but no title, use a short title fallback.
        if not e.get("title") and desc:
            e["title"] = _truncate_words(desc, 14, 160)
            md["title_source"] = md.get(
                "title_source") or "description_fallback"

        # 2) If still no title, look around definition chunk.
        if not e.get("title"):
            rx = _identifier_regex(e)
            def_chunks = (
                md.get("definition_chunks")
                or ([md["chunk_index"]] if md.get("chunk_index") is not None else [])
            )

            found = False

            for ci in def_chunks[:1]:
                chunk = by_idx.get(ci)
                if not chunk:
                    continue

                lines = _chunk_text(chunk).splitlines()
                if not rx:
                    continue

                for i, line in enumerate(lines):
                    if not rx.search(line):
                        continue

                    tail = rx.split(line, maxsplit=1)[-1].strip(" \t:–-—")
                    if tail and _looks_like_title(tail):
                        e["title"] = tail
                        md["title_source"] = "inline_fallback"
                        found = True
                        break

                    for j in range(i + 1, min(i + 8, len(lines))):
                        cand = lines[j].strip()
                        if not cand:
                            continue

                        if _looks_like_title(cand):
                            e["title"] = cand
                            md["title_source"] = "next_line_fallback"
                            found = True

                            if not md.get("description"):
                                d = _collect_desc(lines, j + 1, max_desc_chars)
                                if d:
                                    md["description"] = d
                                    md["description_source"] = "next_paragraph_fallback"
                            break

                        # Do not skip past sentence-like content.
                        break

                    if found:
                        break

                if found:
                    break

            # 3) If id ended the chunk, try start of next chunk.
            if not found:
                for ci in def_chunks[:1]:
                    nxt = by_idx.get(ci + 1)
                    if not nxt:
                        continue

                    lines = _chunk_text(nxt).splitlines()
                    for idx, line in enumerate(lines):
                        cand = line.strip()
                        if not cand:
                            continue

                        if _looks_like_title(cand):
                            e["title"] = cand
                            md["title_source"] = "next_chunk_start_fallback"

                            if not md.get("description"):
                                d = _collect_desc(
                                    lines, idx + 1, max_desc_chars)
                                if d:
                                    md["description"] = d
                                    md["description_source"] = "next_paragraph_fallback"
                            found = True
                        break

                    if found:
                        break

        # 4) If title exists but description does not, try capturing paragraph.
        if e.get("title") and not md.get("description"):
            d = _capture_description_for_entity(e, by_idx, max_desc_chars)
            if d:
                md["description"] = d
                md["description_source"] = md.get(
                    "description_source") or "paragraph_fallback"

    return entities


# ------------------------------------------------------------- noise handling

def split_reference_noise(
    entities: list[dict],
    keep_reference: bool = False,
) -> tuple[list[dict], list[dict]]:
    primary: list[dict] = []
    mentions: list[dict] = []

    for e in entities:
        md = e.get("metadata") or {}

        if md.get("candidate_kind") == "reference":
            ident = str(e.get("identifier") or "").strip()

            noise = (
                not md.get("label")
                and (
                    PURE_NUM_RE.match(ident)
                    or ROMAN_RE.match(ident)
                    or len(ident) <= 2
                )
            )

            if noise:
                md["dropped_reason"] = "noise_reference"
                mentions.append(e)
                continue

            md["mention_only"] = True
            if keep_reference:
                primary.append(e)
            else:
                mentions.append(e)
            continue

        primary.append(e)

    return primary, mentions


# ----------------------------------------------------------- parent resolution

def _rank_for_label(label: str | None, extractor=None) -> int | None:
    label = str(label or "").strip().lower()
    if not label:
        return None

    if extractor is not None:
        profile = getattr(extractor, "profile", None)
        label_rank = getattr(profile, "label_rank", None) or {}
        for k, v in label_rank.items():
            if str(k).strip().lower() == label:
                return int(v)

    return DEFAULT_RANK.get(label)


def _get_entity_rank(entity: dict, extractor=None) -> int | None:
    md = entity.get("metadata") or {}
    return _rank_for_label(md.get("label"), extractor)


def _first_definition_chunk(entity: dict) -> int:
    md = entity.get("metadata") or {}
    chunks = md.get("definition_chunks") or []
    if chunks:
        return int(chunks[0])

    v = md.get("chunk_index")
    return int(v) if v is not None else 10**9


def _offset_in_chunk(entity: dict, chunk) -> int:
    if not chunk:
        return 0

    rx = _identifier_regex(entity)
    if not rx:
        return 0

    m = rx.search(_chunk_text(chunk))
    return m.start() if m else 0


def _parse_heading(heading: str, extractor=None) -> dict | None:
    text = str(heading or "").strip()
    if not text or extractor is None or not hasattr(extractor, "_find_hits"):
        return None

    try:
        hits = extractor._find_hits(text)
    except Exception:
        return None

    if not hits:
        return None

    h = hits[0]
    if int(getattr(h, "start", 0)) > 3:
        return None

    label = str(getattr(h, "label", "") or "").strip().lower()
    display = str(getattr(h, "display", "") or "").strip()
    nid = str(getattr(h, "nid", "") or display.casefold())
    kind = str(getattr(h, "kind", "") or "")

    return {
        "key": f"{kind}:{nid}",
        "kind": kind,
        "label": label,
        "display": display,
        "rank": _rank_for_label(label, extractor),
        "text": text,
    }


def _choose_container(candidates: list[dict], current_chunk: int) -> dict | None:
    if not candidates:
        return None

    unique: list[dict] = []
    seen = set()

    for c in candidates:
        k = entity_key(c)
        if k not in seen:
            seen.add(k)
            unique.append(c)

    before = [c for c in unique if _first_definition_chunk(c) <= current_chunk]
    if before:
        return max(before, key=_first_definition_chunk)

    return min(unique, key=lambda c: abs(_first_definition_chunk(c) - current_chunk))


def _set_parent(entity: dict, parent: dict, reason: str) -> None:
    if not parent:
        return

    md = entity.setdefault("metadata", {})
    pkey = (parent.get("metadata") or {}).get(
        "entity_key") or entity_key(parent)

    md["parent_key"] = pkey
    md["parent_qualified"] = qualified_name(parent)
    md["parent_resolution"] = reason

    if not entity.get("parent_identifier"):
        entity["parent_identifier"] = parent.get("identifier")


def _heading_parent(
    entity: dict,
    chunks_by_idx: dict[int, object],
    extractor,
    label_id_index: dict[tuple[str, str], list[dict]],
) -> dict | None:
    md = entity.get("metadata") or {}
    rank = _get_entity_rank(entity, extractor)
    if rank is None:
        return None

    def_chunks = (
        md.get("definition_chunks")
        or ([md["chunk_index"]] if md.get("chunk_index") is not None else [])
    )

    for ci in def_chunks[:1]:
        chunk = chunks_by_idx.get(ci)
        if not chunk:
            continue

        parsed = []
        self_idx = None

        for idx, h in enumerate(_chunk_headings(chunk)):
            p = _parse_heading(h, extractor)
            if p:
                parsed.append((idx, p))

            if _match_entity_in_text(entity, str(h)):
                self_idx = idx

        scan = parsed if self_idx is None else [
            (i, p) for i, p in parsed if i < self_idx]

        for _, p in reversed(scan):
            prank = p.get("rank")
            if prank is None or prank >= rank:
                continue

            cands = label_id_index.get(
                (p["label"], _norm_id(p["display"])), [])
            parent = _choose_container(cands, ci)

            if parent and entity_key(parent) != entity_key(entity):
                return parent

    return None


def resolve_parents(
    entities: list[dict],
    chunks: list[object],
    extractor=None,
) -> list[dict]:
    chunks_by_idx = {_chunk_index(c): c for c in chunks}

    id_index: dict[str, list[dict]] = defaultdict(list)
    label_id_index: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for e in entities:
        md = e.get("metadata") or {}
        if md.get("candidate_kind") == "reference":
            continue

        id_index[_norm_id(e.get("identifier"))].append(e)
        for alias in md.get("identifier_aliases", []) or []:
            id_index[_norm_id(alias)].append(e)

        label = str(md.get("label") or "").strip().lower()
        if label:
            label_id_index[(label, _norm_id(e.get("identifier")))].append(e)
            for alias in md.get("identifier_aliases", []) or []:
                label_id_index[(label, _norm_id(alias))].append(e)

    # 1) Dotted hierarchy.
    for e in entities:
        md = e.get("metadata") or {}
        if md.get("candidate_kind") == "reference" or md.get("parent_key"):
            continue

        ident = str(e.get("identifier") or "")
        if "." not in ident:
            continue

        candidates = []
        orig = md.get("original_identifier")

        for val in [ident, orig]:
            if val and "." in val:
                parent = val.rsplit(".", 1)[0]
                candidates.extend([parent, normalize_code_identifier(parent)])

        for pid in candidates:
            matches = id_index.get(_norm_id(pid), [])
            if not matches:
                continue

            parent = _choose_container(matches, _first_definition_chunk(e))
            if parent and entity_key(parent) != entity_key(e):
                _set_parent(e, parent, "dotted")
                break

    # 2) Heading-path containment for labelled entities.
    for e in entities:
        md = e.get("metadata") or {}
        if md.get("candidate_kind") == "reference" or md.get("parent_key"):
            continue
        if not md.get("label"):
            continue

        parent = _heading_parent(e, chunks_by_idx, extractor, label_id_index)
        if parent:
            _set_parent(e, parent, "heading_path")

    # 3) Document-order containment fallback.
    ranked = []
    for e in entities:
        md = e.get("metadata") or {}
        if md.get("candidate_kind") == "reference":
            continue

        rank = _get_entity_rank(e, extractor)
        if rank is None:
            continue

        ci = _first_definition_chunk(e)
        off = _offset_in_chunk(e, chunks_by_idx.get(ci))
        ranked.append((ci, off, rank, e))

    ranked.sort(key=lambda x: (x[0], x[1]))

    stack: list[tuple[int, dict]] = []
    for _, _, rank, e in ranked:
        while stack and stack[-1][0] >= rank:
            stack.pop()

        if stack and not (e.get("metadata") or {}).get("parent_key"):
            _set_parent(e, stack[-1][1], "document_order")

        stack.append((rank, e))

    # Finalize qualified names.
    for e in entities:
        md = e.setdefault("metadata", {})
        md["qualified_identifier"] = qualified_name(e)

    return entities


# ------------------------------------------------------------------- stats

def build_stats(entities: list[dict], mentions: list[dict]) -> dict:
    defs = [
        e
        for e in entities
        if (e.get("metadata") or {}).get("candidate_kind") == "definition"
    ]
    inferred = [
        e
        for e in entities
        if (e.get("metadata") or {}).get("candidate_kind") == "inferred"
    ]

    by_type = defaultdict(int)
    for e in entities:
        by_type[_etype_name(e.get("entity_type"))] += 1

    with_title = sum(1 for e in defs if e.get("title"))
    with_desc = sum(1 for e in defs if (
        e.get("metadata") or {}).get("description"))
    neither = sum(
        1
        for e in defs
        if not e.get("title") and not (e.get("metadata") or {}).get("description")
    )

    parents_resolved = sum(
        1
        for e in entities
        if (e.get("metadata") or {}).get("parent_key")
    )

    gaps = [
        qualified_name(e)
        for e in defs
        if not e.get("title") and not (e.get("metadata") or {}).get("description")
    ]

    noise_references = sum(
        1
        for m in mentions
        if (m.get("metadata") or {}).get("dropped_reason") == "noise_reference"
    )

    return {
        "definitions": len(defs),
        "inferred": len(inferred),
        "mentions": len(mentions),
        "noise_references": noise_references,
        "by_type": dict(by_type),
        "with_title": with_title,
        "with_description": with_desc,
        "neither": neither,
        "parents_resolved": parents_resolved,
        "gaps": gaps,
    }


# ------------------------------------------------------------------- entry

def postprocess_entities(
    entities: list[dict],
    chunks: list[object],
    extractor=None,
    infer_missing: bool = True,
    keep_reference: bool = False,
) -> tuple[list[dict], list[dict], dict]:
    entities = [dict(e) for e in entities]

    for e in entities:
        e.setdefault("metadata", {})

    entities = normalize_identifiers(entities)
    entities = merge_duplicate_entities(entities)

    if infer_missing:
        entities = infer_missing_intermediate_entities(entities)

    entities = fill_titles_and_descriptions(entities, chunks)
    entities, mentions = split_reference_noise(
        entities, keep_reference=keep_reference)
    entities = resolve_parents(entities, chunks, extractor=extractor)

    for m in mentions:
        m.setdefault("metadata", {})[
            "qualified_identifier"] = qualified_name(m)

    stats = build_stats(entities, mentions)
    return entities, mentions, stats
