from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..embeds import entry_embed
from ..i18n import normalise, t

if TYPE_CHECKING:
    from ..bot import UnuBot

log = logging.getLogger(__name__)


class FAQ(commands.Cog):
    def __init__(self, bot: UnuBot):
        self.bot = bot

    @app_commands.command(name="faq", description="Antworten auf häufige Fragen / Frequently asked questions")
    @app_commands.describe(thema="Thema — tippe, um vorzuschlagen / topic")
    @app_commands.rename(thema="thema")
    async def faq(self, interaction: discord.Interaction, thema: str) -> None:
        locale = normalise(str(interaction.locale) if interaction.locale else None)
        entry = self.bot.content.lookup_faq(thema)
        if entry is None:
            await interaction.response.send_message(t("not_found", locale), ephemeral=True)
            return
        await interaction.response.send_message(embed=entry_embed(entry, locale))

    @faq.autocomplete("thema")
    async def faq_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = normalise(str(interaction.locale) if interaction.locale else None)
        suggestions = self.bot.content.suggest("faq", current, locale, limit=20)
        return [app_commands.Choice(name=display[:100], value=entry_id) for display, entry_id in suggestions]


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(FAQ(bot))
