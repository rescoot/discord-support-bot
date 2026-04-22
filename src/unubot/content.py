from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rapidfuzz import process as fuzz_process

from .i18n import Locale, pick

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Link:
    url: str
    label: dict[str, str]


@dataclass(frozen=True)
class Entry:
    """A FAQ or glossary entry. Same schema for both — only the folder differs."""

    id: str
    aliases: tuple[str, ...]
    title: dict[str, str]
    body: dict[str, str]
    links: tuple[Link, ...] = ()
    tags: tuple[str, ...] = ()
    source_path: Path | None = None

    def search_terms(self) -> list[str]:
        terms = [self.id, *self.aliases]
        terms.extend(v for v in self.title.values() if v)
        return [t for t in terms if t]

    def localized_title(self, locale: Locale) -> str:
        return pick(self.title, locale) or self.id

    def localized_body(self, locale: Locale) -> str:
        return pick(self.body, locale)


@dataclass(frozen=True)
class DiagnoseStep:
    id: str
    prompt: dict[str, str]
    choices: tuple[DiagnoseChoice, ...] = ()
    answer: dict[str, str] | None = None  # terminal step if set
    links: tuple[Link, ...] = ()


@dataclass(frozen=True)
class DiagnoseChoice:
    label: dict[str, str]
    goto: str


@dataclass(frozen=True)
class DiagnoseFlow:
    id: str
    title: dict[str, str]
    description: dict[str, str]
    start: str
    steps: dict[str, DiagnoseStep]

    def localized_title(self, locale: Locale) -> str:
        return pick(self.title, locale) or self.id


@dataclass
class ContentStore:
    faq: dict[str, Entry] = field(default_factory=dict)
    glossary: dict[str, Entry] = field(default_factory=dict)
    diagnose: dict[str, DiagnoseFlow] = field(default_factory=dict)
    welcome: dict[Locale, str] = field(default_factory=dict)

    def lookup_faq(self, query: str) -> Entry | None:
        return _lookup(self.faq, query)

    def lookup_glossary(self, query: str) -> Entry | None:
        return _lookup(self.glossary, query)

    def suggest(
        self, kind: str, query: str, locale: Locale, limit: int = 20
    ) -> list[tuple[str, str]]:
        """Return [(display, id)] autocomplete suggestions."""
        source: dict[str, Entry] = getattr(self, kind, {})
        if not source:
            return []
        choices: dict[str, str] = {}
        for entry in source.values():
            display = f"{entry.localized_title(locale)} ({entry.id})"
            for term in entry.search_terms():
                choices[term] = entry.id
                choices[display] = entry.id
        if not query:
            seen: set[str] = set()
            out: list[tuple[str, str]] = []
            for entry in source.values():
                if entry.id in seen:
                    continue
                seen.add(entry.id)
                out.append((f"{entry.localized_title(locale)}", entry.id))
                if len(out) >= limit:
                    break
            return out
        hits = fuzz_process.extract(query, list(choices.keys()), limit=limit * 3)
        seen_ids: set[str] = set()
        out = []
        for term, _score, _idx in hits:
            entry_id = choices[term]
            if entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            entry = source[entry_id]
            out.append((entry.localized_title(locale), entry.id))
            if len(out) >= limit:
                break
        return out


def _lookup(store: dict[str, Entry], query: str) -> Entry | None:
    if not query:
        return None
    q = query.strip().lower()
    if q in store:
        return store[q]
    for entry in store.values():
        if q == entry.id.lower() or q in (a.lower() for a in entry.aliases):
            return entry
    # fall back to fuzzy match
    terms: dict[str, str] = {}
    for entry in store.values():
        for term in entry.search_terms():
            terms[term.lower()] = entry.id
    if not terms:
        return None
    best = fuzz_process.extractOne(q, list(terms.keys()), score_cutoff=80)
    if best is None:
        return None
    return store[terms[best[0]]]


def load_content(content_dir: Path) -> ContentStore:
    store = ContentStore()
    store.faq = _load_entries(content_dir / "faq")
    store.glossary = _load_entries(content_dir / "glossary")
    store.diagnose = _load_diagnose(content_dir / "diagnose")
    store.welcome = _load_welcome(content_dir / "welcome")
    log.info(
        "content loaded: faq=%d glossary=%d diagnose=%d welcome=%s",
        len(store.faq),
        len(store.glossary),
        len(store.diagnose),
        sorted(store.welcome),
    )
    return store


def _load_entries(directory: Path) -> dict[str, Entry]:
    if not directory.is_dir():
        return {}
    out: dict[str, Entry] = {}
    for path in sorted(directory.glob("*.yaml")):
        raw = _read_yaml(path)
        if not raw:
            continue
        entry_id = str(raw.get("id") or path.stem).strip().lower()
        entry = Entry(
            id=entry_id,
            aliases=tuple(str(a).strip() for a in raw.get("aliases", []) if str(a).strip()),
            title=_coerce_text(raw.get("title"), entry_id),
            body=_coerce_text(raw.get("body"), ""),
            links=tuple(_coerce_link(lnk) for lnk in raw.get("links", []) if lnk),
            tags=tuple(str(t) for t in raw.get("tags", [])),
            source_path=path,
        )
        if entry.id in out:
            log.warning("duplicate entry id %r in %s", entry.id, path)
        out[entry.id] = entry
    return out


def _load_diagnose(directory: Path) -> dict[str, DiagnoseFlow]:
    if not directory.is_dir():
        return {}
    out: dict[str, DiagnoseFlow] = {}
    for path in sorted(directory.glob("*.yaml")):
        raw = _read_yaml(path)
        if not raw:
            continue
        flow_id = str(raw.get("id") or path.stem).strip().lower()
        steps_raw = raw.get("steps") or {}
        steps: dict[str, DiagnoseStep] = {}
        for step_id, step_raw in steps_raw.items():
            steps[str(step_id)] = DiagnoseStep(
                id=str(step_id),
                prompt=_coerce_text(step_raw.get("prompt"), ""),
                choices=tuple(
                    DiagnoseChoice(
                        label=_coerce_text(c.get("label"), ""),
                        goto=str(c.get("goto", "")),
                    )
                    for c in step_raw.get("choices", [])
                ),
                answer=_coerce_text(step_raw["answer"], "") if "answer" in step_raw else None,
                links=tuple(_coerce_link(lnk) for lnk in step_raw.get("links", []) if lnk),
            )
        flow = DiagnoseFlow(
            id=flow_id,
            title=_coerce_text(raw.get("title"), flow_id),
            description=_coerce_text(raw.get("description"), ""),
            start=str(raw.get("start", "")),
            steps=steps,
        )
        if flow.start and flow.start not in flow.steps:
            log.warning("flow %s: start step %r not found", flow.id, flow.start)
        for step in flow.steps.values():
            for choice in step.choices:
                if choice.goto and choice.goto not in flow.steps:
                    log.warning(
                        "flow %s step %s: choice goto %r missing", flow.id, step.id, choice.goto
                    )
        out[flow.id] = flow
    return out


def _load_welcome(directory: Path) -> dict[Locale, str]:
    out: dict[Locale, str] = {}
    if not directory.is_dir():
        return out
    for locale in ("de", "en"):
        path = directory / f"{locale}.md"
        if path.is_file():
            out[locale] = path.read_text(encoding="utf-8").strip()
    return out


def _read_yaml(path: Path) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        log.error("invalid yaml in %s: %s", path, e)
        return None
    if not isinstance(data, dict):
        log.error("expected mapping at top level of %s, got %r", path, type(data).__name__)
        return None
    return data


def _coerce_text(value: Any, default: str) -> dict[str, str]:
    """Accept either a plain string (applied to all locales) or a {de, en} mapping."""
    if value is None:
        return {"de": default, "en": default}
    if isinstance(value, str):
        return {"de": value, "en": value}
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if v is not None}
    return {"de": str(value), "en": str(value)}


def _coerce_link(raw: Any) -> Link:
    if isinstance(raw, str):
        return Link(url=raw, label={"de": raw, "en": raw})
    url = str(raw.get("url", "")).strip()
    label_raw = raw.get("label") or raw.get("text") or url
    return Link(url=url, label=_coerce_text(label_raw, url))
