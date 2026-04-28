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


class Admin(commands.Cog):
    def __init__(self, bot: UnuBot):
        self.bot = bot

    @app_commands.command(name="reload", description="Reload content from disk (owner only)")
    async def reload(self, interaction: discord.Interaction) -> None:
        locale = resolve_locale(
            self.bot.prefs.get(interaction.user.id),
            str(interaction.locale) if interaction.locale else None,
        )
        if interaction.user.id not in self.bot.config.owner_ids:
            await interaction.response.send_message(t("reload_denied", locale), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            store = self.bot.reload_content()
        except Exception as e:
            log.exception("reload failed")
            await interaction.followup.send(f"Reload failed: {e}", ephemeral=True)
            return
        await interaction.followup.send(
            t(
                "reload_ok",
                locale,
                faq=len(store.faq),
                glossary=len(store.glossary),
                diagnose=len(store.diagnose),
            ),
            ephemeral=True,
        )


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(Admin(bot))
