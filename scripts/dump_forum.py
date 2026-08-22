"""Dump the support forum (threads plus full message history) to JSONL.

Read-only. Pulls the bot token and the forum id straight from .env via the
normal Config, so no credentials need to be passed around.

Needs the Message Content intent enabled for the application and
Read Message History on the forum.

    python scripts/dump_forum.py [--out state/support_dump] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from unubot.config import Config  # noqa: E402

log = logging.getLogger("dump_forum")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _message_record(m: discord.Message) -> dict:
    return {
        "id": m.id,
        "author": {
            "id": m.author.id,
            "name": m.author.name,
            "display_name": getattr(m.author, "display_name", m.author.name),
            "bot": m.author.bot,
        },
        "created_at": _iso(m.created_at),
        "edited_at": _iso(m.edited_at),
        "content": m.content,
        "attachments": [
            {"filename": a.filename, "url": a.url, "content_type": a.content_type}
            for a in m.attachments
        ],
        "embeds": [e.to_dict() for e in m.embeds],
        "reactions": [{"emoji": str(r.emoji), "count": r.count} for r in m.reactions],
        "reply_to": m.reference.message_id if m.reference else None,
        "pinned": m.pinned,
    }


def _thread_record(t: discord.Thread) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "owner_id": t.owner_id,
        "created_at": _iso(t.created_at or discord.utils.snowflake_time(t.id)),
        "archived": t.archived,
        "locked": t.locked,
        "message_count": t.message_count,
        "applied_tags": [{"id": tag.id, "name": tag.name, "emoji": str(tag.emoji or "")} for tag in t.applied_tags],
        "messages": [],
    }


class Dumper(discord.Client):
    def __init__(self, config: Config, out_dir: Path, limit: int | None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.out_dir = out_dir
        self.limit = limit
        self.failed = False

    async def on_ready(self) -> None:
        try:
            await self._dump()
        except Exception:
            self.failed = True
            log.exception("dump failed")
        finally:
            await self.close()

    async def _collect_threads(self, forum: discord.ForumChannel) -> list[discord.Thread]:
        threads: dict[int, discord.Thread] = {t.id: t for t in forum.threads}
        for t in await forum.guild.active_threads():
            if t.parent_id == forum.id:
                threads[t.id] = t
        async for t in forum.archived_threads(limit=None):
            threads[t.id] = t
        ordered = sorted(
            threads.values(),
            key=lambda t: t.created_at or discord.utils.snowflake_time(t.id),
            reverse=True,
        )
        return ordered[: self.limit] if self.limit else ordered

    async def _dump(self) -> None:
        forum_id = self.config.support_forum_channel_id
        if not forum_id:
            raise RuntimeError("SUPPORT_FORUM_CHANNEL_ID is not set in .env")
        forum = self.get_channel(forum_id) or await self.fetch_channel(forum_id)
        if not isinstance(forum, discord.ForumChannel):
            raise RuntimeError(f"channel {forum_id} is a {type(forum).__name__}, not a ForumChannel")
        log.info("forum: #%s (guild %s)", forum.name, forum.guild.name)

        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "tags.json").write_text(
            json.dumps(
                [
                    {
                        "id": tag.id,
                        "name": tag.name,
                        "emoji": str(tag.emoji or ""),
                        "moderated": tag.moderated,
                    }
                    for tag in forum.available_tags
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        log.info("%d available tags written", len(forum.available_tags))

        threads = await self._collect_threads(forum)
        log.info("%d threads to dump", len(threads))

        out_path = self.out_dir / "threads.jsonl"
        total_messages = 0
        empty_content = 0
        with out_path.open("w", encoding="utf-8") as fh:
            for i, thread in enumerate(threads, 1):
                record = _thread_record(thread)
                try:
                    async for m in thread.history(limit=None, oldest_first=True):
                        rec = _message_record(m)
                        record["messages"].append(rec)
                        total_messages += 1
                        if not rec["content"] and not rec["attachments"] and not rec["embeds"]:
                            empty_content += 1
                except discord.Forbidden:
                    log.warning("no access to thread %s (%s)", thread.id, thread.name)
                    record["error"] = "forbidden"
                except discord.HTTPException as e:
                    log.warning("history for %s failed: %s", thread.id, e)
                    record["error"] = str(e)
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                log.info(
                    "[%d/%d] %s (%d msgs, tags: %s)",
                    i,
                    len(threads),
                    thread.name[:60],
                    len(record["messages"]),
                    ", ".join(t["name"] for t in record["applied_tags"]) or "-",
                )

        log.info(
            "done: %d threads, %d messages, %d empty (%s)",
            len(threads),
            total_messages,
            empty_content,
            out_path,
        )
        if empty_content > total_messages * 0.5:
            log.warning("more than half the messages came back empty - is the Message Content intent on?")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("state/support_dump"))
    ap.add_argument("--limit", type=int, default=None, help="only the N newest threads")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("discord").setLevel(logging.WARNING)

    config = Config.from_env()
    client = Dumper(config, args.out.resolve(), args.limit)
    client.run(config.token, log_handler=None)
    return 1 if client.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
