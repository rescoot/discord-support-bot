from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock

from .i18n import SUPPORTED, Locale

log = logging.getLogger(__name__)


class PrefStore:
    """Per-user content language overrides, persisted as JSON.

    Single-process bot, but the file is written from inside coroutines, so a
    lock keeps concurrent writes from corrupting each other.
    """

    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, Locale] = {}
        self._lock = Lock()
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warning("could not read prefs at %s: %s — starting empty", self.path, e)
            return
        if not isinstance(raw, dict):
            log.warning("prefs at %s is not a JSON object — ignoring", self.path)
            return
        for k, v in raw.items():
            if isinstance(v, str) and v in SUPPORTED:
                self._data[str(k)] = v  # type: ignore[assignment]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".prefs-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    def get(self, user_id: int) -> Locale | None:
        return self._data.get(str(user_id))

    def set(self, user_id: int, locale: Locale) -> None:
        with self._lock:
            self._data[str(user_id)] = locale
            self._save()

    def clear(self, user_id: int) -> None:
        with self._lock:
            if self._data.pop(str(user_id), None) is not None:
                self._save()
