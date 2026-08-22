from __future__ import annotations

import logging
from collections import OrderedDict
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from ..embeds import entry_embed
from ..i18n import Locale, resolve_locale, t

if TYPE_CHECKING:
    from ..bot import UnuBot

log = logging.getLogger(__name__)


# Map forum channel id -> content key in store.forum_welcome.
# For now there's only one forum we auto-respond to. If we add more, we'll
# either add more env vars or move to a content-driven mapping.
def _forum_key_for(thread: discord.Thread, support_forum_id: int | None) -> str | None:
    if support_forum_id and thread.parent_id == support_forum_id:
        return "support"
    return None


def _format_tags(names: list[str]) -> str:
    return ", ".join(f"**{n}**" for n in names)


class ForumWelcome(commands.Cog):
    """Auto-responses in the support forum.

    A new post gets the FAQ entries its forum tags map to (see
    content/forum_tags.yaml), or, if the tags map to nothing, the "how to ask"
    checklist. Never both: a post that already has an answer under it doesn't
    need to be told how to write itself.

    Discord can redeliver MESSAGE_CREATE for the same forum starter (e.g. across
    a gateway resume), and mods retag posts repeatedly, so both paths keep a
    bounded record of what they already said in a thread.
    """

    _RECENT_MAX = 512

    def __init__(self, bot: UnuBot):
        self.bot = bot
        self._welcomed: OrderedDict[int, None] = OrderedDict()
        self._suggested: OrderedDict[int, set[str]] = OrderedDict()

    def _mark_welcomed(self, thread_id: int) -> bool:
        if thread_id in self._welcomed:
            return False
        self._welcomed[thread_id] = None
        while len(self._welcomed) > self._RECENT_MAX:
            self._welcomed.popitem(last=False)
        return True

    def _fresh_suggestions(self, thread_id: int, entry_ids: list[str]) -> list[str]:
        """Drop entry ids already posted in this thread, and record the rest."""
        seen = self._suggested.get(thread_id)
        if seen is None:
            seen = set()
            self._suggested[thread_id] = seen
            while len(self._suggested) > self._RECENT_MAX:
                self._suggested.popitem(last=False)
        fresh = [eid for eid in entry_ids if eid not in seen]
        seen.update(fresh)
        return fresh

    def _locale_for(self, thread: discord.Thread) -> Locale:
        """Threads have no locale of their own, so go by the poster's preference."""
        pref = self.bot.prefs.get(thread.owner_id) if thread.owner_id else None
        return resolve_locale(pref)

    def _embeds_for(self, entry_ids: list[str], locale: Locale) -> list[discord.Embed]:
        embeds = []
        for entry_id in entry_ids:
            entry = self.bot.content.faq.get(entry_id)
            if entry is None:
                log.warning("forum_tags.yaml points at missing FAQ entry %r", entry_id)
                continue
            embeds.append(entry_embed(entry, locale))
        return embeds

    async def _send(
        self, thread: discord.Thread, content: str, embeds: list[discord.Embed]
    ) -> None:
        try:
            await thread.send(content=content or None, embeds=embeds)
        except discord.Forbidden:
            log.warning(
                "missing perms to post in thread %s (parent=%s)", thread.id, thread.parent_id
            )
        except discord.HTTPException as e:
            log.warning("auto-response in thread %s failed: %s", thread.id, e)

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message) -> None:
        # Posting in forum threads on `on_thread_create` races the starter
        # message and gets Forbidden. By the time on_message fires for the
        # starter, the thread is fully postable.
        if msg.author.bot:
            return
        if not isinstance(msg.channel, discord.Thread):
            return
        key = _forum_key_for(msg.channel, self.bot.config.support_forum_channel_id)
        if key is None:
            return
        # Forum thread starter messages have id == thread.id; replies don't.
        if msg.id != msg.channel.id:
            return
        if not self._mark_welcomed(msg.channel.id):
            log.debug("already welcomed thread %s, skipping duplicate", msg.channel.id)
            return

        thread = msg.channel
        locale = self._locale_for(thread)
        tag_names = [tag.name for tag in thread.applied_tags]
        embeds = self._embeds_for(
            self._fresh_suggestions(
                thread.id, self.bot.content.forum_tags.suggestions_for(tag_names)
            ),
            locale,
        )
        # An actual answer beats a checklist. The welcome is what we fall back
        # to when the tags tell us nothing.
        if embeds:
            text = t("forum_tag_suggestions", locale, tags=_format_tags(tag_names))
        else:
            text = self.bot.content.forum_welcome.get(key, "")
            if not text:
                log.debug("nothing to post for key=%r in thread %s", key, thread.id)
                return
        await self._send(thread, text, embeds)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        """Mods usually fix the tags after the fact, so react to that too.

        Only fires for threads discord.py has cached, which covers the active
        ones. Retagging a long-archived post is not worth waking up for.
        """
        if _forum_key_for(after, self.bot.config.support_forum_channel_id) is None:
            return
        if after.archived or after.locked:
            return
        added = {tag.id for tag in after.applied_tags} - {tag.id for tag in before.applied_tags}
        if not added:
            return
        names = [tag.name for tag in after.applied_tags if tag.id in added]
        entry_ids = self._fresh_suggestions(
            after.id, self.bot.content.forum_tags.suggestions_for(names)
        )
        if not entry_ids:
            return
        locale = self._locale_for(after)
        embeds = self._embeds_for(entry_ids, locale)
        if not embeds:
            return
        await self._send(after, t("forum_tag_suggestions", locale, tags=_format_tags(names)), embeds)


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(ForumWelcome(bot))
