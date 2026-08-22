from __future__ import annotations

import re
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


def test_forum_welcome_support_loaded(store):
    text = store.forum_welcome.get("support")
    assert text, "support forum welcome missing"
    assert len(text) <= 2000, "forum welcome must fit a single Discord message"


def test_howto_ask_loaded(store):
    text = store.howto.get("ask")
    assert text, "howto/ask template missing"
    assert len(text) <= 2000, "howto template must fit a single Discord message"


def test_bodies_are_not_hard_wrapped(store):
    """Discord turns every newline into a line break, so bodies must not be
    wrapped in the source. One line per paragraph or list item."""
    for entry in {**store.faq, **store.glossary}.values():
        for locale, body in entry.body.items():
            in_code = False
            lines = body.splitlines()
            for i, line in enumerate(lines[:-1]):
                if line.strip().startswith("```"):
                    in_code = not in_code
                if in_code or not line.strip():
                    continue
                nxt = lines[i + 1].strip()
                # a bold heading legitimately ends a line; "**" is its closing run
                assert not (
                    nxt and nxt[0].islower() and not line.rstrip().endswith((":", ".", "**"))
                ), (
                    f"{entry.id} [{locale}] line {i + 1} looks hard-wrapped: {line[-40:]!r}"
                )


def test_markdown_lists_are_preceded_by_a_blank_line(store):
    """Without one, Discord pulls the first list marker up into the paragraph."""
    marker = re.compile(r"^(?:[-*]\s|\d+[.)]\s)")
    for entry in {**store.faq, **store.glossary}.values():
        for locale, body in entry.body.items():
            lines = body.splitlines()
            for i, line in enumerate(lines):
                if i and marker.match(line) and lines[i - 1].strip() and not marker.match(lines[i - 1]):
                    raise AssertionError(
                        f"{entry.id} [{locale}] line {i + 1}: list needs a blank line before it"
                    )


def test_bodies_carry_no_trailing_whitespace(store):
    """Discord strips it on store, so keeping it means a re-rendered embed never
    matches the posted one."""
    for entry in {**store.faq, **store.glossary}.values():
        for locale, body in entry.body.items():
            assert body == body.strip(), f"{entry.id} [{locale}] has surrounding whitespace"
