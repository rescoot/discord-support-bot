"""Persistent language-toggle button used on FAQ, glossary, welcome, diagnose.

Each click flips the visible message into the *target* language encoded in the
button's custom_id, saves the user's preference, and replaces the view with a
fresh button pointing at the opposite language.

We use ``discord.ui.DynamicItem`` so the bot can re-bind buttons after a
restart from nothing but their custom_id — no in-memory state needed.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, ClassVar

import discord

from .embeds import entry_embed
from .i18n import Locale, other, t

if TYPE_CHECKING:
    from .bot import UnuBot

log = logging.getLogger(__name__)

BUTTON_LABEL: dict[Locale, str] = {
    "en": "🇬🇧 Show in English",
    "de": "🇩🇪 Auf Deutsch anzeigen",
}

DENIED_DE = "Nur die Person, die den Befehl ausgeführt hat, kann die Sprache wechseln."
DENIED_EN = "Only the person who ran the command can switch the language."

# id slug accepted in custom_id values: lowercase letters, digits, dash, underscore.
_SLUG = r"[a-z0-9_-]+"
_LOC = r"de|en"
_REQ = r"\d+"


def _toggle_label(target: Locale) -> str:
    return BUTTON_LABEL[target]


def _denied(locale: Locale) -> str:
    return DENIED_DE if locale == "de" else DENIED_EN


def make_view(*items: discord.ui.Item) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for item in items:
        view.add_item(item)
    return view


def _bot(interaction: discord.Interaction) -> UnuBot:
    return interaction.client  # type: ignore[return-value]


class FaqLocaleToggle(
    discord.ui.DynamicItem[discord.ui.Button],
    template=rf"ub:lo:f:(?P<eid>{_SLUG}):(?P<req>{_REQ}):(?P<tgt>{_LOC})",
):
    KIND: ClassVar[str] = "faq"

    def __init__(self, entry_id: str, requester_id: int, target: Locale):
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=_toggle_label(target),
                custom_id=f"ub:lo:f:{entry_id}:{requester_id}:{target}",
            )
        )
        self.entry_id = entry_id
        self.requester_id = requester_id
        self.target: Locale = target

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str]
    ) -> FaqLocaleToggle:
        return cls(match["eid"], int(match["req"]), match["tgt"])  # type: ignore[arg-type]

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = _bot(interaction)
        if interaction.user.id != self.requester_id:
            current = bot.prefs.get(interaction.user.id) or "de"
            await interaction.response.send_message(_denied(current), ephemeral=True)
            return
        entry = bot.content.lookup_faq(self.entry_id)
        if entry is None:
            await interaction.response.send_message(t("not_found", self.target), ephemeral=True)
            return
        bot.prefs.set(self.requester_id, self.target)
        next_target: Locale = other(self.target)
        view = make_view(FaqLocaleToggle(self.entry_id, self.requester_id, next_target))
        await interaction.response.edit_message(embed=entry_embed(entry, self.target), view=view)


class GlossaryLocaleToggle(
    discord.ui.DynamicItem[discord.ui.Button],
    template=rf"ub:lo:g:(?P<eid>{_SLUG}):(?P<req>{_REQ}):(?P<tgt>{_LOC})",
):
    KIND: ClassVar[str] = "glossary"

    def __init__(self, entry_id: str, requester_id: int, target: Locale):
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=_toggle_label(target),
                custom_id=f"ub:lo:g:{entry_id}:{requester_id}:{target}",
            )
        )
        self.entry_id = entry_id
        self.requester_id = requester_id
        self.target: Locale = target

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str]
    ) -> GlossaryLocaleToggle:
        return cls(match["eid"], int(match["req"]), match["tgt"])  # type: ignore[arg-type]

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = _bot(interaction)
        if interaction.user.id != self.requester_id:
            current = bot.prefs.get(interaction.user.id) or "de"
            await interaction.response.send_message(_denied(current), ephemeral=True)
            return
        entry = bot.content.lookup_glossary(self.entry_id)
        if entry is None:
            await interaction.response.send_message(t("not_found", self.target), ephemeral=True)
            return
        bot.prefs.set(self.requester_id, self.target)
        next_target: Locale = other(self.target)
        view = make_view(GlossaryLocaleToggle(self.entry_id, self.requester_id, next_target))
        await interaction.response.edit_message(embed=entry_embed(entry, self.target), view=view)


class WelcomeLocaleToggle(
    discord.ui.DynamicItem[discord.ui.Button],
    template=rf"ub:lo:w:(?P<req>{_REQ}):(?P<tgt>{_LOC})",
):
    KIND: ClassVar[str] = "welcome"

    def __init__(self, recipient_id: int, target: Locale):
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=_toggle_label(target),
                custom_id=f"ub:lo:w:{recipient_id}:{target}",
            )
        )
        self.recipient_id = recipient_id
        self.target: Locale = target

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str]
    ) -> WelcomeLocaleToggle:
        return cls(int(match["req"]), match["tgt"])  # type: ignore[arg-type]

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = _bot(interaction)
        if interaction.user.id != self.recipient_id:
            current = bot.prefs.get(interaction.user.id) or "de"
            await interaction.response.send_message(_denied(current), ephemeral=True)
            return
        text = bot.content.welcome.get(self.target) or bot.content.welcome.get("de", "")
        if not text:
            return
        bot.prefs.set(self.recipient_id, self.target)
        next_target: Locale = other(self.target)
        view = make_view(WelcomeLocaleToggle(self.recipient_id, next_target))
        await interaction.response.edit_message(content=text, view=view)


class DiagnoseLocaleToggle(
    discord.ui.DynamicItem[discord.ui.Button],
    template=rf"ub:lo:d:(?P<fid>{_SLUG}):(?P<sid>{_SLUG}):(?P<req>{_REQ}):(?P<tgt>{_LOC})",
):
    """Toggle button for diagnose. Used on the start step and terminal answers.

    Re-renders the *current* step in the target locale, including the choice
    buttons. Goes through the diagnose cog's view factory to keep all the
    interactive bits consistent.
    """

    KIND: ClassVar[str] = "diagnose"

    def __init__(self, flow_id: str, step_id: str, requester_id: int, target: Locale):
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=_toggle_label(target),
                custom_id=f"ub:lo:d:{flow_id}:{step_id}:{requester_id}:{target}",
            )
        )
        self.flow_id = flow_id
        self.step_id = step_id
        self.requester_id = requester_id
        self.target: Locale = target

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str]
    ) -> DiagnoseLocaleToggle:
        return cls(match["fid"], match["sid"], int(match["req"]), match["tgt"])  # type: ignore[arg-type]

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = _bot(interaction)
        if interaction.user.id != self.requester_id:
            current = bot.prefs.get(interaction.user.id) or "de"
            await interaction.response.send_message(_denied(current), ephemeral=True)
            return
        flow = bot.content.diagnose.get(self.flow_id)
        step = flow.steps.get(self.step_id) if flow else None
        if flow is None or step is None:
            await interaction.response.send_message(t("not_found", self.target), ephemeral=True)
            return
        bot.prefs.set(self.requester_id, self.target)
        # Imported here to avoid a circular import at module load.
        from .cogs.diagnose import build_step_view, step_embed

        view = build_step_view(flow, step, self.target, self.requester_id)
        await interaction.response.edit_message(embed=step_embed(flow, step, self.target), view=view)


def faq_view(entry_id: str, requester_id: int, current: Locale) -> discord.ui.View:
    return make_view(FaqLocaleToggle(entry_id, requester_id, other(current)))


def glossary_view(entry_id: str, requester_id: int, current: Locale) -> discord.ui.View:
    return make_view(GlossaryLocaleToggle(entry_id, requester_id, other(current)))


def welcome_view(recipient_id: int, current: Locale) -> discord.ui.View:
    return make_view(WelcomeLocaleToggle(recipient_id, other(current)))


def register_dynamic_items(bot: UnuBot) -> None:
    bot.add_dynamic_items(
        FaqLocaleToggle,
        GlossaryLocaleToggle,
        WelcomeLocaleToggle,
        DiagnoseLocaleToggle,
    )
