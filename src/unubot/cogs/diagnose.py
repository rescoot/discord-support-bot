from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..content import DiagnoseFlow, DiagnoseStep
from ..embeds import LIBRESCOOT_COLOR, UNU_COLOR
from ..i18n import Locale, normalise, pick, t

if TYPE_CHECKING:
    from ..bot import UnuBot

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 600  # seconds


class DiagnoseView(discord.ui.View):
    def __init__(self, flow: DiagnoseFlow, step: DiagnoseStep, locale: Locale, user_id: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.flow = flow
        self.step = step
        self.locale = locale
        self.user_id = user_id

        for idx, choice in enumerate(step.choices[:20]):
            label = pick(choice.label, locale) or choice.goto
            button = discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label=label[:80],
                custom_id=f"diag:{flow.id}:{choice.goto}:{idx}",
            )
            button.callback = self._make_callback(choice.goto)
            self.add_item(button)

        # On terminal steps (answer set, no choices), offer restart/close.
        if step.answer or not step.choices:
            restart = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=t("diagnose_restart", locale),
                custom_id=f"diag:{flow.id}:__restart__",
            )
            restart.callback = self._make_callback(flow.start)
            self.add_item(restart)

        cancel = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label=t("diagnose_cancel", locale),
            custom_id=f"diag:{flow.id}:__cancel__",
        )
        cancel.callback = self._cancel
        self.add_item(cancel)

    def _make_callback(self, goto: str):
        async def cb(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    t("reload_denied", self.locale), ephemeral=True
                )
                return
            next_step = self.flow.steps.get(goto)
            if next_step is None:
                await interaction.response.edit_message(
                    embed=_step_embed(self.flow, self.step, self.locale), view=None
                )
                return
            view = DiagnoseView(self.flow, next_step, self.locale, self.user_id)
            await interaction.response.edit_message(
                embed=_step_embed(self.flow, next_step, self.locale), view=view
            )

        return cb

    async def _cancel(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(t("reload_denied", self.locale), ephemeral=True)
            return
        await interaction.response.edit_message(
            content=t("diagnose_cancelled", self.locale), embed=None, view=None
        )


def _step_embed(flow: DiagnoseFlow, step: DiagnoseStep, locale: Locale) -> discord.Embed:
    is_terminal = step.answer is not None
    color = LIBRESCOOT_COLOR if is_terminal else UNU_COLOR
    title = flow.localized_title(locale)
    if is_terminal:
        title = f"✅ {title}"
    body = pick(step.answer, locale) if is_terminal else pick(step.prompt, locale)
    embed = discord.Embed(title=title, description=body or "", color=color)
    if step.links:
        embed.add_field(
            name=t("more_info", locale),
            value="\n".join(
                f"• [{pick(link.label, locale) or link.url}]({link.url})"
                for link in step.links[:8]
            ),
            inline=False,
        )
    embed.set_footer(text=f"/diagnose {flow.id} · {step.id}")
    return embed


class Diagnose(commands.Cog):
    def __init__(self, bot: UnuBot):
        self.bot = bot

    @app_commands.command(
        name="diagnose",
        description="Geführte Fehlersuche / guided troubleshooter",
    )
    @app_commands.describe(flow="Welcher Diagnoseablauf / which flow")
    async def diagnose(self, interaction: discord.Interaction, flow: str) -> None:
        locale = normalise(str(interaction.locale) if interaction.locale else None)
        flows = self.bot.content.diagnose
        chosen = flows.get(flow.strip().lower())
        if chosen is None:
            await interaction.response.send_message(t("not_found", locale), ephemeral=True)
            return
        start = chosen.steps.get(chosen.start)
        if start is None:
            await interaction.response.send_message(
                "Flow has no start step", ephemeral=True
            )
            log.error("flow %s: start step %r missing", chosen.id, chosen.start)
            return
        view = DiagnoseView(chosen, start, locale, interaction.user.id)
        await interaction.response.send_message(
            embed=_step_embed(chosen, start, locale), view=view
        )

    @diagnose.autocomplete("flow")
    async def diagnose_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = normalise(str(interaction.locale) if interaction.locale else None)
        flows = self.bot.content.diagnose
        choices: list[app_commands.Choice[str]] = []
        q = current.strip().lower()
        for flow in flows.values():
            display = flow.localized_title(locale)
            if not q or q in flow.id.lower() or q in display.lower():
                choices.append(app_commands.Choice(name=f"{display} ({flow.id})"[:100], value=flow.id))
        return choices[:25]


async def setup(bot: UnuBot) -> None:
    await bot.add_cog(Diagnose(bot))
