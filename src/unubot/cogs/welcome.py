from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from ..i18n import Locale, normalise, t

if TYPE_CHECKING:
    from ..bot import UnuBot

log = logging.getLogger(__name__)


def _pick_locale(member: discord.Member) -> Locale:
    """Pick the best locale for a joining member.

    Discord doesn't expose a per-member locale; we fall back to the guild's
    preferred locale. New members from an English-speaking Discord region
    will get English, everyone else defaults to German.
    """
    guild_locale = getattr(member.guild, "preferred_locale", None)
    return normalise(str(guild_locale) if guild_locale else None)


class Welcome(commands.Cog):
    def __init__(self, bot: UnuBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        locale = _pick_locale(member)
        text = self.bot.content.welcome.get(locale) or self.bot.content.welcome.get("de", "")
        if not text:
            return

        try:
            await member.send(text)
            return
        except (discord.Forbidden, discord.HTTPException) as e:
            log.info(t("welcome_dm_failed_log", locale, user=str(member)))
            log.debug("dm error: %s", e)

        # Fallback: post in the configured channel if the user didn't allow DMs.
        fallback = self.bot.config.welcome_fallback_channel_id
        if not fallback:
            return
        channel = self.bot.get_channel(fallback)
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(f"{member.mention}\n{text}")
            except discord.HTTPException as e:
                log.warning("fallback welcome to channel %s failed: %s", fallback, e)


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(Welcome(bot))
