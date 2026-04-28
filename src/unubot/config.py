from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    owner_ids: frozenset[int]
    dev_guild_id: int | None
    welcome_fallback_channel_id: int | None
    log_level: str
    content_dir: Path
    state_dir: Path

    @classmethod
    def from_env(cls, content_dir: Path | None = None) -> Config:
        load_dotenv()
        token = os.environ.get("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")

        owners = {
            int(x) for x in os.environ.get("OWNER_IDS", "").split(",") if x.strip().isdigit()
        }
        dev_guild = os.environ.get("DEV_GUILD_ID", "").strip()
        fallback = os.environ.get("WELCOME_FALLBACK_CHANNEL_ID", "").strip()

        return cls(
            token=token,
            owner_ids=frozenset(owners),
            dev_guild_id=int(dev_guild) if dev_guild.isdigit() else None,
            welcome_fallback_channel_id=int(fallback) if fallback.isdigit() else None,
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            content_dir=content_dir or _default_content_dir(),
            state_dir=_default_state_dir(),
        )


def _default_content_dir() -> Path:
    override = os.environ.get("UNUBOT_CONTENT_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    here = Path(__file__).resolve().parent
    for parent in (here, *here.parents):
        candidate = parent / "content"
        if candidate.is_dir():
            return candidate
    raise RuntimeError("Could not locate content/ directory")


def _default_state_dir() -> Path:
    override = os.environ.get("UNUBOT_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    here = Path(__file__).resolve().parent
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent / "state"
    return Path.cwd() / "state"
