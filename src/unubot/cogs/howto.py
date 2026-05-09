from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..i18n import resolve_locale, t

if TYPE_CHECKING:
    from ..bot import UnuBot

log = logging.getLogger(__name__)


class Howto(commands.Cog):
    def __init__(self, bot: UnuBot):
        self.bot = bot

    howto = app_commands.Group(
        name="howto",
        description="Vorlagen für Mods / templates for mods",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def _allowed(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in self.bot.config.owner_ids:
            return True
        perms = interaction.permissions
        return perms.manage_guild or perms.manage_messages

    async def _post_topic(self, interaction: discord.Interaction, key: str) -> None:
        locale = resolve_locale(
            self.bot.prefs.get(interaction.user.id),
            str(interaction.locale) if interaction.locale else None,
        )
        if not self._allowed(interaction):
            await interaction.response.send_message(t("howto_denied", locale), ephemeral=True)
            return
        text = self.bot.content.howto.get(key)
        if not text:
            await interaction.response.send_message(
                t("howto_missing", locale, key=key), ephemeral=True
            )
            return
        channel = interaction.channel
        if channel is None or not hasattr(channel, "send"):
            await interaction.response.send_message(
                t("howto_no_channel", locale), ephemeral=True
            )
            return
        try:
            await channel.send(text)
        except discord.Forbidden:
            await interaction.response.send_message(
                t("howto_forbidden", locale), ephemeral=True
            )
            return
        except discord.HTTPException as e:
            log.warning("howto post failed in channel %s: %s", channel.id, e)
            await interaction.response.send_message(
                t("howto_failed", locale, error=str(e)), ephemeral=True
            )
            return
        await interaction.response.send_message(t("howto_posted", locale), ephemeral=True)

    @howto.command(name="ask", description="Wie man hier um Hilfe fragt / how to ask for help")
    async def ask(self, interaction: discord.Interaction) -> None:
        await self._post_topic(interaction, "ask")


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(Howto(bot))
