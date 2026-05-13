from __future__ import annotations

import logging
from collections import OrderedDict
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

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


class ForumWelcome(commands.Cog):
    # Discord can redeliver MESSAGE_CREATE for the same forum starter (e.g.
    # across a gateway resume), which would post the welcome twice. Track
    # recently-welcomed thread ids and skip repeats. Bounded so memory can't
    # grow forever.
    _RECENT_MAX = 512

    def __init__(self, bot: UnuBot):
        self.bot = bot
        self._welcomed: OrderedDict[int, None] = OrderedDict()

    def _mark_welcomed(self, thread_id: int) -> bool:
        if thread_id in self._welcomed:
            return False
        self._welcomed[thread_id] = None
        while len(self._welcomed) > self._RECENT_MAX:
            self._welcomed.popitem(last=False)
        return True

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

        text = self.bot.content.forum_welcome.get(key)
        if not text:
            log.debug("no forum_welcome content for key=%r, skipping thread %s", key, msg.channel.id)
            return

        if not self._mark_welcomed(msg.channel.id):
            log.debug("already welcomed thread %s, skipping duplicate", msg.channel.id)
            return

        try:
            await msg.channel.send(text)
        except discord.Forbidden:
            log.warning(
                "missing perms to post in thread %s (parent=%s)",
                msg.channel.id,
                msg.channel.parent_id,
            )
        except discord.HTTPException as e:
            log.warning("forum welcome to thread %s failed: %s", msg.channel.id, e)


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(ForumWelcome(bot))
