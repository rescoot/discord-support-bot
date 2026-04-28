from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..embeds import entry_embed
from ..i18n import resolve_locale, t
from ..locale_view import glossary_view

if TYPE_CHECKING:
    from ..bot import UnuBot

log = logging.getLogger(__name__)


class Glossary(commands.Cog):
    def __init__(self, bot: UnuBot):
        self.bot = bot

    def _locale(self, interaction: discord.Interaction):
        return resolve_locale(
            self.bot.prefs.get(interaction.user.id),
            str(interaction.locale) if interaction.locale else None,
        )

    @app_commands.command(
        name="glossar",
        description="Technische Begriffe erklärt / explain a technical term",
    )
    @app_commands.describe(begriff="Begriff — z. B. MDB, DBC, AUX, CBB / term")
    async def glossary(self, interaction: discord.Interaction, begriff: str) -> None:
        locale = self._locale(interaction)
        entry = self.bot.content.lookup_glossary(begriff)
        if entry is None:
            await interaction.response.send_message(t("not_found", locale), ephemeral=True)
            return
        view = glossary_view(entry.id, interaction.user.id, locale)
        await interaction.response.send_message(embed=entry_embed(entry, locale), view=view)

    @glossary.autocomplete("begriff")
    async def glossary_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = self._locale(interaction)
        suggestions = self.bot.content.suggest("glossary", current, locale, limit=20)
        return [
            app_commands.Choice(name=display[:100], value=entry_id) for display, entry_id in suggestions
        ]


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(Glossary(bot))
