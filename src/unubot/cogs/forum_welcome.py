from __future__ import annotations

import logging
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
    def __init__(self, bot: UnuBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        if not isinstance(thread.parent, discord.ForumChannel):
            return

        key = _forum_key_for(thread, self.bot.config.support_forum_channel_id)
        if key is None:
            return

        text = self.bot.content.forum_welcome.get(key)
        if not text:
            log.debug("no forum_welcome content for key=%r, skipping thread %s", key, thread.id)
            return

        try:
            await thread.send(text)
        except discord.Forbidden:
            log.warning("missing perms to post in thread %s (parent=%s)", thread.id, thread.parent_id)
        except discord.HTTPException as e:
            log.warning("forum welcome to thread %s failed: %s", thread.id, e)


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(ForumWelcome(bot))
