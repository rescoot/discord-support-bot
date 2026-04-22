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


class Glossary(commands.Cog):
    def __init__(self, bot: UnuBot):
        self.bot = bot

    @app_commands.command(
        name="glossar",
        description="Technische Begriffe erklärt / explain a technical term",
    )
    @app_commands.describe(begriff="Begriff — z. B. MDB, DBC, AUX, CBB / term")
    async def glossary(self, interaction: discord.Interaction, begriff: str) -> None:
        locale = normalise(str(interaction.locale) if interaction.locale else None)
        entry = self.bot.content.lookup_glossary(begriff)
        if entry is None:
            await interaction.response.send_message(t("not_found", locale), ephemeral=True)
            return
        await interaction.response.send_message(embed=entry_embed(entry, locale))

    @glossary.autocomplete("begriff")
    async def glossary_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = normalise(str(interaction.locale) if interaction.locale else None)
        suggestions = self.bot.content.suggest("glossary", current, locale, limit=20)
        return [
            app_commands.Choice(name=display[:100], value=entry_id) for display, entry_id in suggestions
        ]


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(Glossary(bot))
