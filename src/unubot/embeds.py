from __future__ import annotations

import discord

from .content import Entry, Link
from .i18n import Locale, pick, t

UNU_COLOR = discord.Color.from_str("#F90F0F")  # admin red from the server palette
LIBRESCOOT_COLOR = discord.Color.from_str("#9B59B6")  # entwickler purple


def entry_embed(entry: Entry, locale: Locale, footer: str | None = None) -> discord.Embed:
    body = entry.localized_body(locale) or t("not_found", locale)
    color = LIBRESCOOT_COLOR if "librescoot" in entry.tags else UNU_COLOR
    embed = discord.Embed(
        title=entry.localized_title(locale),
        description=body[:4000],
        color=color,
    )
    if entry.links:
        embed.add_field(
            name=t("more_info", locale),
            value="\n".join(f"• [{pick(lnk.label, locale) or lnk.url}]({lnk.url})" for lnk in entry.links[:8]),
            inline=False,
        )
    if entry.aliases:
        embed.set_footer(text=footer or f"alias: {', '.join(entry.aliases[:6])}")
    elif footer:
        embed.set_footer(text=footer)
    return embed


def link_line(link: Link, locale: Locale) -> str:
    return f"[{pick(link.label, locale) or link.url}]({link.url})"
