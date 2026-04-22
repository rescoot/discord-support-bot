from __future__ import annotations

import asyncio
import logging
import sys

from .bot import UnuBot
from .config import Config


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.getLogger("discord.http").setLevel("WARNING")


async def _run() -> None:
    config = Config.from_env()
    _configure_logging(config.log_level)
    bot = UnuBot(config)
    async with bot:
        await bot.start(config.token)


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
