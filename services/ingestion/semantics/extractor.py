"""Deterministic, document-agnostic extraction of structural entity candidates.

Design
------
Layer 1 (per chunk): scan line by line and emit *candidates*, each tagged with
the kind of evidence that produced it (heading > line-start > table-row >
reference).

Layer 2 (per document): merge candidates that denote the same entity, pick the
best evidence, attach title/description, resolve parents against entities that
actually exist, and drop unlabelled noise (version numbers, units) that has no
structural corroboration.

Nothing here knows about SOC 2, GDPR, ISO, etc. Framework knowledge enters only
through ``ExtractionProfile`` (label vocabulary), which is data, not code.

Use ``extract_document(chunks)`` for real work. ``extract(chunk)`` is kept for
backwards compatibility and only sees one chunk.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Iterable, Mapping

from services.ingestion.chunking.models import DocumentChunk
from services.ingestion.semantics.models import (
    SemanticEntity,
    SemanticEntityType,
    SemanticValidationStatus,
)

_T = SemanticEntityType

# Label -> entity type. Types not in the enum fall back to SECTION/OTHER; the
# exact label is always preserved in metadata["label"]. Add CHAPTER/ANNEX/...
# to SemanticEntityType when downstream needs to distinguish them.
DEFAULT_LABELS: dict[str, SemanticEntityType] = {
    "article": _T.ARTICLE,
    "recital": _T.RECITAL,
    "section": _T.SECTION,
    "chapter": _T.SECTION,
    "part": _T.SECTION,
    "annex": _T.SECTION,
    "appendix": _T.SECTION,
    "schedule": _T.SECTION,
    "clause": _T.SECTION,
    "control": _T.CONTROL,
    "requirement": _T.CONTROL,
    "criterion": _T.CONTROL,
}


@dataclass(frozen=True)
class ExtractionProfile:
    labels: Mapping[str, SemanticEntityType] = field(
        default_factory=lambda: dict(DEFAULT_LABELS)
    )
    # Labels that may carry roman-numeral or single-letter ids (Chapter III, Annex A).
    alpha_id_labels: frozenset[str] = frozenset(
        {"chapter", "part", "annex", "appendix", "schedule", "section"}
    )
    # Containment order for labels that nest (lower number = bigger container).
    # Used to scope ids that restart per container (Section 1 in every Chapter).
    label_rank: Mapping[str, int] = field(
        default_factory=lambda: {
            "part": 0, "chapter": 1, "annex": 1, "appendix": 1,
            "schedule": 1, "section": 2, "article": 3,
        }
    )
    max_title_chars: int = 400
    max_title_words: int = 60


class Evidence(IntEnum):
    REFERENCE = 0
    TABLE_ROW = 1
    LINE_START = 2
    HEADING = 3


_BASE_CONFIDENCE = {
    Evidence.REFERENCE: 0.35,
    Evidence.TABLE_ROW: 0.70,
    Evidence.LINE_START: 0.75,
    Evidence.HEADING: 0.80,
}

_NOISE_CHARS = " \t-–—•*#>|"
_WS = re.compile(r"\s+")
_LEADING_NOISE = re.compile(r"^[\s\-–—:.)]+")
_TRAILING_NOISE = re.compile(r"[\s.;,:]+$")
_TITLE_SEP = re.compile(r"^\s*[:\-–—]\s*")
# Flattened table cell: ", Column header = value"
_ROW_HEADER = re.compile(r",\s*[^,=]{1,120}?\s*=\s*")
_ROW_CELL = re.compile(r"[^,=]{1,120}?\s*=\s*(?P<v>.*)$", re.S)
# "Article 6 of Directive ..." -> belongs to another instrument.
_EXTERNAL = re.compile(
    r"^\s*(?:of|under)\s+(?!this\b|the present\b)(?:the\s+)?(?:\w+\s+){0,2}?"
    r"(?:directive|regulation|decision|treaty|convention|act|agreement|standard)\b"
    # "Article 263 TFEU": id followed by an instrument acronym
    r"|^\s*(?-i:[A-Z]{3,8})\b",
    re.I,
)
_OUTLINE = re.compile(r"^[ \t]*(?P<id>\d+(?:\.\d+)+)\.?[ \t]+(?=[A-Za-z])")
_CODE = re.compile(r"(?<![\w.])[A-Z]{1,10}(?:[.-]?\d+)(?:\.\d+)+(?!\w)")


def _clean(text: str | None) -> str:
    text = _WS.sub(" ", text or "").strip()
    text = _LEADING_NOISE.sub("", text)
    return _TRAILING_NOISE.sub("", text).strip(" \t,;:.–—-")


@dataclass(frozen=True)
class _Hit:
    start: int
    end: int
    kind: str  # label ("article"), "code" or "outline"
    label: str
    display: str
    nid: str
    locator: str
    scheme: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.nid}"


@dataclass(frozen=True)
class _Candidate:
    kind: str
    nid: str
    display: str
    label: str
    scheme: str
    evidence: Evidence
    chunk_index: int
    title: str | None = None
    description: str | None = None
    locator: str = ""
    title_source: str = "inline"
    scope: str = ""      # container key, set only when the same id repeats per container
    container: str = ""  # nearest enclosing higher-rank definition (final key)

    @property
    def raw_key(self) -> str:
        return f"{self.kind}:{self.nid}"

    @property
    def key(self) -> str:
        return f"{self.raw_key}@{self.scope}" if self.scope else self.raw_key


class SemanticEntityExtractor:
    """Extract candidate structural entities without an LLM."""

    def __init__(self, profile: ExtractionProfile | None = None) -> None:
        self.profile = profile or ExtractionProfile()
        labels = "|".join(
            re.escape(label)
            for label in sorted(self.profile.labels, key=len, reverse=True)
        )
        self._labelled = re.compile(
            r"(?<!\w)(?P<label>" + labels + r")\s+(?:"
            r"\(?(?P<num>\d+(?:\.\d+)*[a-z]?)\)?"
            r"(?P<loc>(?:\([0-9A-Za-z]{1,4}\))*)"
            r"|(?P<alpha>(?-i:[IVXLCDM]{1,7}|[A-Z]))"
            r")(?!\w)",
            re.IGNORECASE,
        )

    # ------------------------------------------------------------------ API

    def extract_document(
        self, chunks: Iterable[DocumentChunk], framework: str = "unknown"
    ) -> list[SemanticEntity]:
        chunks = list(chunks)
        candidates: list[_Candidate] = []
        for i, chunk in enumerate(chunks):
            nxt = chunks[i + 1] if i + 1 < len(chunks) else None
            candidates.extend(self.extract_candidates(chunk, next_chunk=nxt))
        return self._resolve(candidates, framework, document_scope=True)

    def extract(
        self, chunk: DocumentChunk, framework: str = "unknown"
    ) -> list[SemanticEntity]:
        """Single-chunk view (no cross-chunk merging or noise pruning)."""
        return self._resolve(
            self.extract_candidates(chunk), framework, document_scope=False
        )

    def _next_chunk_title(self, next_chunk) -> str | None:
        """Title for an id that ends a chunk: the next chunk's heading/first line."""
        for heading in next_chunk.metadata.get("headings", []) or []:
            if self._looks_like_heading(str(heading)):
                return str(heading).strip()
        for line in next_chunk.text.split("\n"):
            if line.strip():
                return line if self._looks_like_heading(line) else None
        return None

    def extract_candidates(
        self, chunk: DocumentChunk, next_chunk: DocumentChunk | None = None
    ) -> list[_Candidate]:
        idx = chunk.chunk_index
        out: list[_Candidate] = []
        for heading in chunk.metadata.get("headings", []) or []:
            out.extend(self._scan_line(
                str(heading).strip(), idx, heading=True))

        lines = chunk.text.split("\n")
        for n, line in enumerate(lines):
            if not line.strip():
                continue
            j = n + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            source = "next_line"
            if j < len(lines):
                nxt = lines[j]
            else:
                nxt = self._next_chunk_title(
                    next_chunk) if next_chunk else None
                source = "next_chunk"
            out.extend(self._scan_line(line, idx, nxt, next_source=source))
        return out

    # ------------------------------------------------------------- scanning

    def _find_hits(self, line: str) -> list[_Hit]:
        hits: list[_Hit] = []
        for m in self._labelled.finditer(line):
            label = m.group("label").lower()
            num, alpha = m.group("num"), m.group("alpha")
            if num is None and label not in self.profile.alpha_id_labels:
                continue
            display = num or alpha
            hits.append(
                _Hit(m.start(), m.end(), label, label, display,
                     display.casefold(), m.group("loc") or "", "")
            )
        taken = [(h.start, h.end) for h in hits]

        def free(s: int, e: int) -> bool:
            return not any(s < te and ts < e for ts, te in taken)

        for m in _CODE.finditer(line):
            if free(m.start(), m.end()):
                code = m.group()
                scheme = re.match(r"[A-Z]+", code).group()
                hits.append(
                    _Hit(m.start(), m.end(), "code", "", code,
                         code.casefold(), "", scheme)
                )
        om = _OUTLINE.match(line)
        if om and free(om.start("id"), om.end()):
            hits.append(
                _Hit(om.start("id"), om.end(), "outline", "", om.group("id"),
                     om.group("id"), "", "")
            )
        hits.sort(key=lambda h: h.start)
        return hits

    @staticmethod
    def _is_boundary(line: str, start: int) -> bool:
        prefix = line[:start].rstrip()
        return not prefix.strip(_NOISE_CHARS) or prefix.endswith((".", ";", "|"))

    def _split(self, text: str) -> tuple[str | None, str | None]:
        """Return (title, description). Sentence-like text is a description."""
        text = _clean(text)
        if not text or "=" in text:
            return None, None
        if (
            len(text) > self.profile.max_title_chars
            or len(text.split()) > self.profile.max_title_words
        ):
            return None, text
        return text, None

    @staticmethod
    def _cell_value(value: str) -> str | None:
        nxt = _ROW_HEADER.search(value)
        if nxt:
            value = value[: nxt.start()]
        return _clean(value) or None

    def _parse_tail(self, tail: str) -> tuple[str | None, str | None, bool]:
        """Parse text after an identifier -> (title, description, is_table_row)."""
        tail = tail.strip()
        if not tail:
            return None, None, False
        if tail.startswith(","):
            cell = _ROW_CELL.match(tail[1:].lstrip())
            if not cell:
                return None, None, False
            return None, self._cell_value(cell.group("v")), True
        sep = _TITLE_SEP.match(tail)
        if not sep:
            return None, None, False
        body = tail[sep.end():]
        row = _ROW_HEADER.search(body)
        if row:
            title, long_title = self._split(body[: row.start()])
            desc = self._cell_value(body[row.end():]) or long_title
            return title, desc, True
        title, desc = self._split(body)
        return title, desc, False

    def is_bare_identifier(self, text: str) -> bool:
        """True if the whole text is just an id ("Article 6", "CC1.1", "CHAPTER III")."""
        s = text.strip().rstrip(".:–—- ")
        hits = self._find_hits(s)
        return bool(hits) and hits[0].start == 0 and hits[0].end >= len(s) \
            and hits[0].kind != "outline"

    def _looks_like_heading(self, line: str) -> bool:
        s = line.strip()
        if not s or len(s) > 120 or s[-1] in ".;:,":
            return False
        if s[0] in "-•*(#>|" or s[0].isdigit() or not s[0].isupper():
            return False
        if len(s.split()) > 15:
            return False
        hits = self._find_hits(s)
        return not (hits and hits[0].start <= 2)

    def _scan_line(
        self,
        line: str,
        chunk_index: int,
        next_line: str | None = None,
        heading: bool = False,
        next_source: str = "next_line",
    ) -> list[_Candidate]:
        hits = self._find_hits(line)
        out: list[_Candidate] = []
        row_key, row_end = None, -1

        for i, h in enumerate(hits):
            if heading and i > 0:
                break
            if h.key == row_key and h.start < row_end:
                continue  # repeated id inside the row we just parsed

            at_boundary = self._is_boundary(line, h.start)
            if heading and not at_boundary:
                break

            seg_end = next(
                (n.start for n in hits[i + 1:]
                 if self._is_boundary(line, n.start)),
                len(line),
            )
            tail = line[h.end:seg_end]
            rest_empty = not line[h.end:].strip()
            prefix_empty = not line[: h.start].strip(_NOISE_CHARS)

            title = desc = None
            row = False
            title_source = "inline"
            if h.kind == "outline":
                title, desc = self._split(tail)
            else:
                title, desc, row = self._parse_tail(tail)
                if heading and not (title or desc) and tail.strip():
                    title, _ = self._split(tail)
            if desc and desc.casefold().startswith(h.display.casefold()):
                desc = None  # merged-cell echo of the id itself

            if (
                not heading and h.kind != "outline" and at_boundary
                and not (title or desc or row) and rest_empty
                and next_line and self._looks_like_heading(next_line)
            ):
                title, _ = self._split(next_line)
                title_source = next_source

            if h.kind == "outline":
                is_def = bool(title)
            else:
                is_def = at_boundary and (
                    bool(title or desc) or row or (prefix_empty and rest_empty)
                )

            if is_def:
                ev = (
                    Evidence.HEADING if heading
                    else Evidence.TABLE_ROW if row
                    else Evidence.LINE_START
                )
                row_key, row_end = h.key, seg_end
            else:
                if heading or h.kind == "outline":
                    continue
                if h.label and _EXTERNAL.match(line[h.end: h.end + 80]):
                    continue  # reference into another instrument
                ev = Evidence.REFERENCE
                title = desc = None

            out.append(
                _Candidate(
                    kind=h.kind, nid=h.nid, display=h.display, label=h.label,
                    scheme=h.scheme, evidence=ev, chunk_index=chunk_index,
                    title=title, description=desc, locator=h.locator,
                    title_source=title_source,
                )
            )
        return out

    # ----------------------------------------------------------- resolution

    def _assign_scopes(self, cands: list[_Candidate]) -> list[_Candidate]:
        """Qualify ids that repeat under different containers.

        "Section 1" defined under Chapter III and again under Chapter IV are two
        entities. Detection is structural: same id, different enclosing container.
        References to such ids are dropped, because they cannot be resolved here.
        """
        rank = self.profile.label_rank
        if not any(rank.get(c.label) is not None for c in cands):
            return cands

        stack: list[tuple[int, str]] = []
        containers: dict[str, set[str]] = defaultdict(set)
        for c in cands:
            r = rank.get(c.label)
            if r is None or c.evidence == Evidence.REFERENCE:
                continue
            while stack and stack[-1][0] >= r:
                stack.pop()
            if stack:
                containers[c.raw_key].add(stack[-1][1])
            stack.append((r, c.raw_key))
        ambiguous = {k for k, v in containers.items() if len(v) > 1}

        out: list[_Candidate] = []
        stack = []
        for c in cands:
            r = rank.get(c.label)
            if r is None:
                out.append(c)
                continue
            if c.evidence == Evidence.REFERENCE:
                if c.raw_key not in ambiguous:
                    out.append(c)
                continue
            while stack and stack[-1][0] >= r:
                stack.pop()
            container = stack[-1][1] if stack else ""
            scope = container if (c.raw_key in ambiguous and container) else ""
            final = c.raw_key + (f"@{scope}" if scope else "")
            out.append(replace(c, scope=scope, container=container))
            stack.append((r, final))
        return out

    @staticmethod
    def _parent_nid(nid: str) -> str | None:
        return nid.rsplit(".", 1)[0] if "." in nid else None

    def _resolve(
        self,
        candidates: list[_Candidate],
        framework: str,
        *,
        document_scope: bool,
    ) -> list[SemanticEntity]:
        candidates = self._assign_scopes(candidates)
        groups: dict[str, list[_Candidate]] = defaultdict(list)
        for c in candidates:
            groups[c.key].append(c)

        defined_ids: dict[str, set[str]] = defaultdict(set)
        defined_schemes: set[str] = set()
        for c in candidates:
            if c.evidence > Evidence.REFERENCE:
                defined_ids[c.kind].add(c.nid)
                if c.kind == "code":
                    defined_schemes.add(c.scheme)

        family: dict[str, dict[str, set[str]]] = {}
        for kind, ids in defined_ids.items():
            fam: dict[str, set[str]] = defaultdict(set)
            for nid in ids:
                parent = self._parent_nid(nid)
                if parent is not None:
                    fam[parent].add(nid)
            family[kind] = fam

        def corroborated(kind: str, nid: str) -> bool:
            fam = family.get(kind, {})
            parent = self._parent_nid(nid)
            if nid in fam:  # has defined children
                return True
            if parent is None:
                return False
            return len(fam.get(parent, ())) > 1 or parent in defined_ids[kind]

        kept: dict[str, list[_Candidate]] = {}
        for key, items in groups.items():
            first = items[0]
            has_def = any(c.evidence > Evidence.REFERENCE for c in items)
            if (
                document_scope and not has_def and first.kind == "code"
                and first.scheme not in defined_schemes
            ):
                continue  # e.g. "TLS1.2": looks like an id, never defined as one
            kept[key] = items

        known: dict[str, dict[str, str]] = defaultdict(dict)
        for items in kept.values():
            known[items[0].kind][items[0].nid] = items[0].display

        entities: list[SemanticEntity] = []
        for key, items in kept.items():
            first = items[0]
            kind, nid = first.kind, first.nid
            defs = [c for c in items if c.evidence > Evidence.REFERENCE]
            refs = [c for c in items if c.evidence == Evidence.REFERENCE]
            best = (
                max(defs, key=lambda c: (c.evidence,
                    bool(c.title))) if defs else first
            )
            # A title cut off by a chunk boundary is a prefix of the complete one
            # seen elsewhere; never let the truncated copy win on evidence rank.
            titled = [c for c in defs if c.title]
            pool = [
                c for c in titled
                if not any(
                    o.title.casefold() != c.title.casefold()
                    and o.title.casefold().startswith(c.title.casefold())
                    for o in titled
                )
            ] or titled
            title_c = max(pool, key=lambda c: c.evidence, default=None)
            title = title_c.title if title_c else None
            description = next(
                (c.description for c in defs if c.description), None)

            if first.label:
                is_corroborated = True
            elif defs:
                is_corroborated = corroborated(kind, nid)
            else:
                is_corroborated = (
                    first.scheme in defined_schemes if document_scope else True
                )

            conf = _BASE_CONFIDENCE[best.evidence]
            if kind == "outline":
                conf -= 0.15
            if first.label:
                conf += 0.10
            if title:
                conf += 0.05
            if not is_corroborated:
                conf = min(conf, 0.40)
            conf = round(min(conf, 0.95), 2)

            parent_display = None
            parts = nid.split(".")
            for i in range(len(parts) - 1, 0, -1):
                base = ".".join(parts[:i])
                for cand in (base, base + ".0"):
                    if cand != nid and cand in known[kind]:
                        parent_display = known[kind][cand]
                        break
                if parent_display:
                    break
            # Flag a missing *intermediate* level (e.g. A1.2.1 absent while A1.2.1.1
            # exists). Roots such as CC1.0 (expected "CC1") are not orphans.
            expected = first.display.rsplit(
                ".", 1)[0] if "." in first.display else ""
            parent_hint = (
                expected
                if "." in expected
                and expected.casefold() not in known[kind]
                and expected.casefold() + ".0" not in known[kind]
                else None
            )

            def_chunks = sorted({c.chunk_index for c in defs})
            ref_chunks = sorted(
                {c.chunk_index for c in refs} - set(def_chunks))
            metadata = {
                "chunk_index": def_chunks[0] if def_chunks else first.chunk_index,
                "entity_key": key,
                "label": first.label or None,
                "scheme": first.scheme or None,
                "depth": nid.count(".") + 1,
                "extraction_method": best.evidence.name.lower(),
                "candidate_kind": "definition" if defs else "reference",
                "title_source": title_c.title_source if title_c else None,
                "description": description,
                "definition_chunks": def_chunks,
                "reference_chunks": ref_chunks[:25],
                "reference_count": len(refs),
                "referenced_locators": sorted({c.locator for c in refs if c.locator})[:10],
                "corroborated": is_corroborated,
                "parent_hint": parent_hint,
                "container_key": best.container,
            }
            metadata = {k: v for k, v in metadata.items()
                        if v not in (None, [], "")}

            entities.append(
                SemanticEntity(
                    framework=framework,
                    identifier=first.display,
                    entity_type=self.profile.labels.get(first.label, _T.OTHER),
                    title=title,
                    parent_identifier=parent_display,
                    confidence=conf,
                    validation_status=SemanticValidationStatus.REVIEW,
                    source="deterministic",
                    metadata=metadata,
                )
            )
        return entities
