from __future__ import annotations

from pathlib import Path

import pytest

from unubot.content import ForumTagMap, load_content

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


@pytest.fixture(scope="module")
def store():
    return load_content(CONTENT_DIR)


def test_forum_tags_loaded(store):
    assert store.forum_tags.tags, "no forum tag mappings loaded"
    assert store.forum_tags.max_suggestions >= 1


def test_forum_tags_reference_existing_faq_entries(store):
    for tag, entry_ids in store.forum_tags.tags.items():
        for entry_id in entry_ids:
            assert entry_id in store.faq, f"tag {tag!r} points at unknown FAQ entry {entry_id!r}"


def test_forum_tag_keys_are_lowercased(store):
    for tag in store.forum_tags.tags:
        assert tag == tag.lower(), f"tag key {tag!r} was not normalised"


def test_suggestions_match_regardless_of_case(store):
    assert store.forum_tags.suggestions_for(["Sitzschloss"])
    assert store.forum_tags.suggestions_for(["sitzschloss"]) == store.forum_tags.suggestions_for(
        ["SITZSCHLOSS"]
    )


def test_suggestions_dedupe_across_tags_and_respect_the_cap():
    tags = ForumTagMap(max_suggestions=2, tags={"a": ("x", "y"), "b": ("y", "z")})
    assert tags.suggestions_for(["a", "b"]) == ["x", "y"]
    assert tags.suggestions_for(["b"]) == ["y", "z"]
    assert tags.suggestions_for(["unmapped"]) == []
    assert tags.suggestions_for([]) == []
