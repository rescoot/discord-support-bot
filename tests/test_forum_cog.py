from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from unubot.cogs.forum_welcome import ForumWelcome, _format_tags
from unubot.content import load_content


class _StubBot:
    """The dedupe bookkeeping doesn't touch the bot, so a bare object is enough."""


def _cog() -> ForumWelcome:
    return ForumWelcome(_StubBot())  # type: ignore[arg-type]


def test_welcome_fires_once_per_thread():
    cog = _cog()
    assert cog._mark_welcomed(1) is True
    assert cog._mark_welcomed(1) is False
    assert cog._mark_welcomed(2) is True


def test_suggestions_are_not_repeated_in_the_same_thread():
    cog = _cog()
    assert cog._fresh_suggestions(1, ["aux-battery", "hard-reset"]) == ["aux-battery", "hard-reset"]
    assert cog._fresh_suggestions(1, ["aux-battery"]) == []
    assert cog._fresh_suggestions(1, ["aux-battery", "cb-battery"]) == ["cb-battery"]
    # a different thread starts clean
    assert cog._fresh_suggestions(2, ["aux-battery"]) == ["aux-battery"]


def test_recent_thread_records_stay_bounded():
    cog = _cog()
    for thread_id in range(ForumWelcome._RECENT_MAX + 50):
        cog._mark_welcomed(thread_id)
        cog._fresh_suggestions(thread_id, ["aux-battery"])
    assert len(cog._welcomed) == ForumWelcome._RECENT_MAX
    assert len(cog._suggested) == ForumWelcome._RECENT_MAX


def test_format_tags():
    assert _format_tags(["Sitzschloss", "Akkuproblem"]) == "**Sitzschloss**, **Akkuproblem**"


class _Bot:
    """Just the three attributes the cog reaches for."""

    def __init__(self, content, forum_id: int = 42):
        self.config = SimpleNamespace(support_forum_channel_id=forum_id)
        self.content = content
        self.prefs = SimpleNamespace(get=lambda user_id: None)


def _thread(thread_id: int = 100, parent_id: int = 42, tags=()) -> MagicMock:
    thread = MagicMock(spec=discord.Thread)
    thread.id = thread_id
    thread.parent_id = parent_id
    thread.owner_id = 7
    thread.archived = False
    thread.locked = False
    thread.applied_tags = [
        SimpleNamespace(id=i, name=name, emoji=None) for i, name in enumerate(tags, start=1)
    ]
    thread.send = AsyncMock()
    return thread


def _starter(thread: MagicMock) -> MagicMock:
    msg = MagicMock(spec=discord.Message)
    msg.id = thread.id  # forum starter messages share the thread id
    msg.channel = thread
    msg.author = SimpleNamespace(bot=False, id=7)
    return msg


@pytest.fixture(scope="module")
def content():
    return load_content(Path(__file__).resolve().parent.parent / "content")


async def test_tagged_starter_post_gets_faq_entries_instead_of_the_checklist(content):
    cog = ForumWelcome(_Bot(content))  # type: ignore[arg-type]
    thread = _thread(tags=["Sitzschloss"])
    await cog.on_message(_starter(thread))

    thread.send.assert_awaited_once()
    kwargs = thread.send.await_args.kwargs
    assert "**Sitzschloss**" in kwargs["content"]
    assert "Willkommen" not in kwargs["content"]
    assert [e.title for e in kwargs["embeds"]] == [
        content.faq[eid].title["de"]
        for eid in content.forum_tags.suggestions_for(["Sitzschloss"])
    ]


async def test_starter_post_in_another_forum_is_ignored(content):
    cog = ForumWelcome(_Bot(content))  # type: ignore[arg-type]
    thread = _thread(parent_id=999, tags=["Sitzschloss"])
    await cog.on_message(_starter(thread))
    thread.send.assert_not_awaited()


async def test_post_whose_tags_map_to_nothing_falls_back_to_the_checklist(content):
    cog = ForumWelcome(_Bot(content))  # type: ignore[arg-type]
    thread = _thread(tags=["Sonstiges"])
    await cog.on_message(_starter(thread))
    kwargs = thread.send.await_args.kwargs
    assert "Willkommen" in kwargs["content"]
    assert kwargs["embeds"] == []


async def test_tag_added_later_posts_only_the_new_entries(content):
    cog = ForumWelcome(_Bot(content))  # type: ignore[arg-type]
    before = _thread(tags=[])
    after = _thread(tags=["Akkuproblem"])
    await cog.on_thread_update(before, after)

    after.send.assert_awaited_once()
    kwargs = after.send.await_args.kwargs
    assert "**Akkuproblem**" in kwargs["content"]
    assert kwargs["embeds"]

    # the same tag applied again says nothing; a new one only adds what's new
    after.send.reset_mock()
    await cog.on_thread_update(after, after)
    after.send.assert_not_awaited()


async def test_retagging_an_archived_post_stays_quiet(content):
    cog = ForumWelcome(_Bot(content))  # type: ignore[arg-type]
    before = _thread(tags=[])
    after = _thread(tags=["Akkuproblem"])
    after.archived = True
    await cog.on_thread_update(before, after)
    after.send.assert_not_awaited()
