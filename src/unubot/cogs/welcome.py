from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from ..i18n import Locale, t
from ..locale_view import welcome_view

if TYPE_CHECKING:
    from ..bot import UnuBot

log = logging.getLogger(__name__)


class Welcome(commands.Cog):
    def __init__(self, bot: UnuBot):
        self.bot = bot

    def _locale_for(self, member: discord.Member) -> Locale:
        # Discord exposes no per-member locale on join, so we default to German
        # (the community is DE-primary). Returning members keep their saved pref.
        return self.bot.prefs.get(member.id) or "de"

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        locale = self._locale_for(member)
        text = self.bot.content.welcome.get(locale) or self.bot.content.welcome.get("de", "")
        if not text:
            return
        view = welcome_view(member.id, locale)

        try:
            await member.send(text, view=view)
            return
        except (discord.Forbidden, discord.HTTPException) as e:
            log.info(t("welcome_dm_failed_log", locale, user=str(member)))
            log.debug("dm error: %s", e)

        fallback = self.bot.config.welcome_fallback_channel_id
        if not fallback:
            return
        channel = self.bot.get_channel(fallback)
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(f"{member.mention}\n{text}", view=view)
            except discord.HTTPException as e:
                log.warning("fallback welcome to channel %s failed: %s", fallback, e)


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(Welcome(bot))
