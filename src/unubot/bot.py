from __future__ import annotations

import logging

import discord
from discord.ext import commands

from .config import Config
from .content import ContentStore, load_content
from .locale_view import register_dynamic_items
from .prefs import PrefStore

log = logging.getLogger(__name__)

COGS = (
    "unubot.cogs.faq",
    "unubot.cogs.glossary",
    "unubot.cogs.welcome",
    "unubot.cogs.diagnose",
    "unubot.cogs.admin",
)


class UnuBot(commands.Bot):
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.members = True  # needed for on_member_join
        intents.message_content = False  # we use slash commands only
        super().__init__(command_prefix="!unused!", intents=intents)
        self.config = config
        self.content: ContentStore = load_content(config.content_dir)
        self.prefs = PrefStore(config.state_dir / "prefs.json")

    def reload_content(self) -> ContentStore:
        self.content = load_content(self.config.content_dir)
        return self.content

    async def setup_hook(self) -> None:
        register_dynamic_items(self)
        for ext in COGS:
            await self.load_extension(ext)
            log.info("loaded %s", ext)

        if self.config.dev_guild_id:
            guild = discord.Object(id=self.config.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("synced %d commands to dev guild %d", len(synced), self.config.dev_guild_id)
        else:
            synced = await self.tree.sync()
            log.info("synced %d global commands", len(synced))

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info("logged in as %s (id=%s)", self.user, self.user.id)
