from __future__ import annotations

from pathlib import Path

import pytest

from unubot.content import load_content

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


@pytest.fixture(scope="module")
def store():
    return load_content(CONTENT_DIR)


def test_faq_loads_with_required_fields(store):
    assert store.faq, "no FAQ entries loaded"
    for entry in store.faq.values():
        assert entry.id
        assert entry.title.get("de"), f"{entry.id}: missing German title"
        assert entry.body.get("de"), f"{entry.id}: missing German body"


def test_glossary_loads_with_required_fields(store):
    assert store.glossary, "no glossary entries loaded"
    for entry in store.glossary.values():
        assert entry.id
        assert entry.title.get("de"), f"{entry.id}: missing German title"
        assert entry.body.get("de"), f"{entry.id}: missing German body"


def test_glossary_aliases_are_unique_across_entries(store):
    seen: dict[str, str] = {}
    for entry in store.glossary.values():
        for alias in entry.aliases:
            assert alias.lower() not in seen or seen[alias.lower()] == entry.id, (
                f"alias {alias!r} used by {seen.get(alias.lower())} and {entry.id}"
            )
            seen[alias.lower()] = entry.id


def test_faq_lookup_by_id_and_alias(store):
    assert store.lookup_faq("aux-battery") is not None
    alias_hit = store.lookup_faq("aux")
    assert alias_hit is not None
    assert alias_hit.id == "aux-battery" or alias_hit.id == "aux"  # fuzzy can match either


def test_diagnose_flows_have_valid_goto_targets(store):
    assert store.diagnose, "no diagnose flows loaded"
    for flow in store.diagnose.values():
        assert flow.start in flow.steps, f"{flow.id}: start {flow.start!r} missing"
        for step in flow.steps.values():
            for choice in step.choices:
                assert choice.goto in flow.steps, (
                    f"{flow.id}/{step.id}: goto {choice.goto!r} missing"
                )
            if not step.choices:
                assert step.answer is not None, (
                    f"{flow.id}/{step.id}: non-terminal step without choices"
                )


def test_welcome_loaded_for_both_locales(store):
    assert store.welcome.get("de"), "German welcome missing"
    assert store.welcome.get("en"), "English welcome missing"
