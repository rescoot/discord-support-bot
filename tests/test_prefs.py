from __future__ import annotations

import json
from pathlib import Path

from unubot.prefs import PrefStore


def test_empty_store_returns_none(tmp_path: Path) -> None:
    store = PrefStore(tmp_path / "p.json")
    assert store.get(123) is None


def test_set_then_get_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    store = PrefStore(path)
    store.set(42, "en")
    assert store.get(42) == "en"
    assert path.is_file()


def test_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    PrefStore(path).set(7, "en")
    again = PrefStore(path)
    assert again.get(7) == "en"


def test_clear_removes_entry(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    store = PrefStore(path)
    store.set(1, "en")
    store.clear(1)
    assert store.get(1) is None
    again = PrefStore(path)
    assert again.get(1) is None


def test_invalid_json_recovers(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text("not json at all", encoding="utf-8")
    store = PrefStore(path)
    assert store.get(1) is None
    store.set(1, "en")
    assert store.get(1) == "en"


def test_unknown_locale_ignored_on_load(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"1": "fr", "2": "en"}), encoding="utf-8")
    store = PrefStore(path)
    assert store.get(1) is None
    assert store.get(2) == "en"


def test_atomic_save_creates_parent_dir(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "nested" / "p.json"
    store = PrefStore(path)
    store.set(99, "de")
    assert path.is_file()
