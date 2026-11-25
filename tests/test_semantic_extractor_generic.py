"""Framework-independent tests for SemanticEntityExtractor.

Fixtures are synthetic on purpose: each one pins a *structural pattern*
(not a SOC 2 / GDPR string), so a regression here means the extractor broke
for every future document that uses that pattern.

Runs with pytest, or directly: python tests/test_semantic_extractor_generic.py
"""
from collections import Counter
from types import SimpleNamespace

from services.ingestion.semantics.extractor import SemanticEntityExtractor

EX = SemanticEntityExtractor()


def chunk(text, idx=0, headings=None):
    return SimpleNamespace(
        text=text, chunk_index=idx, metadata={"headings": headings or []}
    )


def run(*chunks):
    return EX.extract_document(chunks)


def by_key(entities):
    return {e.metadata["entity_key"]: e for e in entities}


def check_invariants(entities):
    """Call on every real document: these must hold regardless of framework."""
    keys = [e.metadata["entity_key"] for e in entities]
    assert len(keys) == len(set(keys)), "duplicate entity keys"
    index = set(keys)
    for e in entities:
        kind = e.metadata["entity_key"].split(":", 1)[0]
        if e.parent_identifier:
            assert f"{kind}:{e.parent_identifier.casefold()}" in index, (
                f"dangling parent {e.parent_identifier} for {e.identifier}"
            )
        if e.title:
            assert len(e.title) <= 400 and "=" not in e.title
        assert 0 < e.confidence <= 0.95


def entity_report(entities):
    """Print this instead of 'first 15 entities'; it shows quality, not volume."""
    defs = [e for e in entities if e.metadata["candidate_kind"] == "definition"]
    print(f"entities={len(entities)} definitions={len(defs)} "
          f"references_only={len(entities) - len(defs)}")
    print("by kind:", dict(
        Counter(e.metadata["entity_key"].split(":")[0] for e in entities)))
    print("titled definitions:", sum(1 for e in defs if e.title), "/", len(defs))
    print("with parent:", sum(1 for e in entities if e.parent_identifier))
    print("parent_hint (orphans):", sum(
        1 for e in entities if "parent_hint" in e.metadata))
    print("uncorroborated:", sum(
        1 for e in entities if not e.metadata["corroborated"]))


# ---------------------------------------------------------------- tests

def test_title_on_multiline_chunk():
    # Regression: old `(.+)$` only matched on the last line of a chunk.
    e = by_key(run(chunk(
        "Article 5 – Principles relating to processing\nPersonal data shall be lawful.")))
    assert e["article:5"].title == "Principles relating to processing"


def test_title_on_next_line_when_id_stands_alone():
    e = by_key(run(chunk(
        "Article 7\n\nConditions for consent\n1. Where processing is based on consent.")))
    assert e["article:7"].title == "Conditions for consent"
    assert e["article:7"].metadata["title_source"] == "next_line"


def test_bullet_after_bare_id_is_not_a_title():
    e = by_key(run(chunk("Article 8\n- processing situations as provided for")))
    assert e["article:8"].title is None
    assert e["article:8"].metadata["candidate_kind"] == "definition"


def test_same_number_different_label_does_not_collide():
    e = by_key(run(chunk("Article 5 – Principles\nSection 5 – Special cases")))
    assert {"article:5", "section:5"} <= set(e)


def test_subparagraph_reference_resolves_to_base_entity():
    ents = by_key(
        run(chunk("as set out in Article 23(1) and Article 6(1)(a).")))
    assert set(ents) == {"article:23", "article:6"}
    assert ents["article:6"].metadata["referenced_locators"] == ["(1)(a)"]
    assert ents["article:6"].metadata["candidate_kind"] == "reference"


def test_external_reference_is_dropped_but_internal_kept():
    assert run(chunk("pursuant to Article 6 of Directive 95/46/EC applies")) == []
    assert "article:6" in by_key(
        run(chunk("pursuant to Article 6 of this Regulation applies")))


def test_article_followed_by_instrument_acronym_is_external():
    assert run(
        chunk("as laid down in Article 263 TFEU and Article 16 TFEU.")) == []
    assert "article:6" in by_key(
        run(chunk("as laid down in Article 6 and Article 7(1) here.")))


def test_version_like_tokens_do_not_become_entities():
    ents = run(chunk("Supports TLS1.2 and TLS1.3 only."),
               chunk("CC1.0: Environment\nCC1.1: Integrity", idx=1))
    ids = {e.identifier for e in ents}
    assert "TLS1.2" not in ids and "TLS1.3" not in ids
    assert {"CC1.0", "CC1.1"} <= ids


def test_parent_resolution_uses_dot_zero_and_never_dangles():
    ents = run(chunk(
        "CC1.0: Environment\nCC1.1: Integrity\nCC1.1.1: Code of conduct is published"))
    e = by_key(ents)
    assert e["code:cc1.1"].parent_identifier == "CC1.0"
    assert e["code:cc1.1.1"].parent_identifier == "CC1.1"
    assert e["code:cc1.0"].parent_identifier is None
    # a root, not an orphan
    assert "parent_hint" not in e["code:cc1.0"].metadata
    check_invariants(ents)


def test_flattened_table_row_gives_title_and_description():
    text = ("CC1.1: Principle one holds, Control Activity = Entity does X. "
            "CC1.1, Test Applied = Inquired of staff. "
            "CC1.2: Principle two, Control Activity = Entity does Y.")
    e = by_key(run(chunk(text)))
    assert len([k for k in e if k.startswith("code:")]) == 2
    assert e["code:cc1.1"].title == "Principle one holds"
    assert e["code:cc1.1"].metadata["description"] == "Entity does X"
    assert e["code:cc1.1"].metadata["extraction_method"] == "table_row"


def test_long_colon_form_text_is_a_title_but_table_cell_is_a_description():
    # Criteria statements can be 30+ words and are titles; ", Header = value" cells are descriptions.
    long = ("The entity implements logical access security software, infrastructure, and architectures "
            "over protected information assets to protect them from security events to meet objectives")
    e = by_key(run(chunk(f"CC6.1: {long}\nCC6.2: Registration\n"
                         "CC6.2.1, Control Activity = Users are registered before access is granted")))
    assert e["code:cc6.1"].title.startswith("The entity implements")
    assert e["code:cc6.2.1"].title is None
    assert "registered" in e["code:cc6.2.1"].metadata["description"]


def test_orphan_hint_only_when_an_intermediate_level_is_missing():
    e = by_key(run(chunk("A1.1: Capacity\nA1.2: Backups\nA1.2.1.1: Deep item")))
    assert e["code:a1.2.1.1"].metadata["parent_hint"] == "A1.2.1"
    assert "parent_hint" not in e["code:a1.1"].metadata


def test_bare_id_at_chunk_end_takes_title_from_next_chunk_heading():
    # The id is the last line of one chunk; the title is the next chunk's heading.
    ents = by_key(run(chunk("1. Previous paragraph text.\nArticle 8", idx=0),
                      chunk("Conditions for child consent\n1. Where point (a) applies.", idx=1,
                            headings=["Conditions for child consent"])))
    assert ents["article:8"].title == "Conditions for child consent"
    assert ents["article:8"].metadata["title_source"] == "next_chunk"


def test_reference_in_one_chunk_merges_with_definition_in_another():
    ents = by_key(run(chunk("see CC6.1 for details.", idx=0),
                      chunk("CC6.1: Logical access\nCC6.2: Registration", idx=5)))
    e = ents["code:cc6.1"]
    assert e.title == "Logical access"
    assert e.metadata["definition_chunks"] == [5]
    assert e.metadata["reference_chunks"] == [0]


def test_roman_numeral_and_letter_ids_need_an_allowed_label():
    e = by_key(
        run(chunk("CHAPTER III\nRights of the data subject\nAnnex A – Forms")))
    assert e["chapter:iii"].title == "Rights of the data subject"
    assert "annex:a" in e
    assert "article:a" not in by_key(run(chunk("Article A person may")))


def test_numeric_outline_needs_siblings():
    e = by_key(run(chunk("5.1 Policies\n5.2 Procedures\n3.5 Mbps")))
    assert e["outline:5.1"].metadata["corroborated"] is True
    assert e["outline:3.5"].metadata["corroborated"] is False
    assert e["outline:3.5"].confidence <= 0.40


def test_heading_evidence_wins_and_does_not_count_as_reference():
    e = by_key(
        run(chunk("body text", headings=[" Article 9 – Special categories"])))
    assert e["article:9"].title == "Special categories"
    assert e["article:9"].metadata["extraction_method"] == "heading"
    assert e["article:9"].metadata["reference_count"] == 0


def test_ids_that_restart_per_container_are_scoped_not_merged():
    text = ("CHAPTER III\nRights\nSection 1\nTransparency\nArticle 12\nInformation\n"
            "CHAPTER IV\nController\nSection 1\nGeneral obligations\nArticle 24\nResponsibility")
    ents = run(chunk(text))
    e = by_key(ents)
    s3, s4 = e["section:1@chapter:iii"], e["section:1@chapter:iv"]
    assert s3.title == "Transparency" and s4.title == "General obligations"
    assert e["article:12"].metadata["container_key"] == "section:1@chapter:iii"
    assert e["article:24"].metadata["container_key"] == "section:1@chapter:iv"
    assert "section:1" not in e  # no unscoped duplicate
    check_invariants(ents)


def test_unique_ids_stay_unscoped_but_still_get_a_container():
    e = by_key(run(chunk("CHAPTER II\nPrinciples\nArticle 5\nLawfulness")))
    assert "article:5" in e
    assert e["article:5"].metadata["container_key"] == "chapter:ii"


def test_truncated_title_at_chunk_edge_loses_to_complete_title():
    e = by_key(run(chunk(
        "CC1.5: COSO Principle 5: The entity holds individuals accountable for objectives, "
        "Control Activity = Does X. CC1.5: COSO Principle 5: The entity holds individuals", 0),
        chunk("CC1.6: Other", 1)))
    assert e["code:cc1.5"].title == "COSO Principle 5: The entity holds individuals accountable for objectives"


def test_label_only_heading_is_merged_into_the_following_heading():
    from services.ingestion.semantics.heading_labels import attach_heading_labels

    def el(kind, text):
        return SimpleNamespace(element_type=SimpleNamespace(value=kind), text=text)

    elements = [el("heading", "Article 6"), el("heading", "Lawfulness of processing"),
                el("list", "1. Processing shall be lawful"),
                el("heading", "Article 7"), el("heading", "Conditions for consent")]
    chunks = [chunk("Lawfulness of processing\n1. Processing shall be lawful", 0, ["Lawfulness of processing"]),
              chunk("Lawfulness of processing\n2. Member States may",
                    1, ["Lawfulness of processing"]),
              chunk("Conditions for consent\n1. Where processing",
                    2, ["Conditions for consent"]),
              chunk("Unrelated text", 3, ["Scope"])]
    assert attach_heading_labels(elements, chunks) == 3
    assert chunks[1].metadata["headings"] == [
        "Article 6 – Lawfulness of processing"]
    assert chunks[3].metadata["headings"] == ["Scope"]

    e = by_key(run(*chunks))
    assert e["article:6"].title == "Lawfulness of processing"
    assert e["article:7"].title == "Conditions for consent"
    assert e["article:6"].metadata["extraction_method"] == "heading"


def test_bare_identifier_detection():
    assert EX.is_bare_identifier(
        "Article 6") and EX.is_bare_identifier("CHAPTER III")
    assert EX.is_bare_identifier("CC1.1")
    assert not EX.is_bare_identifier(
        "Article 6 – Lawfulness") and not EX.is_bare_identifier("Definitions")


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print("FAIL", name, "->", repr(exc))
    raise SystemExit(1 if failed else 0)
