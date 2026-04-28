from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

Locale = Literal["de", "en"]
DEFAULT_LOCALE: Locale = "de"
SUPPORTED: tuple[Locale, ...] = ("de", "en")


def other(locale: Locale) -> Locale:
    return "en" if locale == "de" else "de"


def normalise(locale: str | None) -> Locale:
    """Map a Discord locale string (e.g. 'de', 'en-US') to a supported bot locale.

    Everything that isn't clearly English falls back to German — this community is DE-primary.
    """
    if not locale:
        return DEFAULT_LOCALE
    tag = str(locale).lower().split("-", 1)[0]
    if tag == "en":
        return "en"
    return "de"


def pick(bundle: Mapping[str, str] | str | None, locale: Locale) -> str:
    """Return the best-matching string from a {de: ..., en: ...} bundle.

    Falls back to the other language if the requested one is missing, then to empty string.
    Accepts a bare string for convenience (same text for all locales).
    """
    if bundle is None:
        return ""
    if isinstance(bundle, str):
        return bundle
    if locale in bundle and bundle[locale]:
        return bundle[locale]
    for alt in SUPPORTED:
        if alt in bundle and bundle[alt]:
            return bundle[alt]
    return ""


# UI strings used by the bot itself (not content-driven).
UI: dict[str, dict[Locale, str]] = {
    "not_found": {
        "de": "Dazu habe ich nichts gefunden. Versuch es mit der Auto-Vervollständigung.",
        "en": "No match. Try autocompletion to see available entries.",
    },
    "reload_ok": {
        "de": "Inhalte neu geladen: {faq} FAQ, {glossary} Glossar, {diagnose} Diagnoseflüsse.",
        "en": "Reloaded: {faq} FAQ, {glossary} glossary, {diagnose} diagnose flows.",
    },
    "reload_denied": {
        "de": "Nur Bot-Owner dürfen das.",
        "en": "Owner-only command.",
    },
    "diagnose_restart": {"de": "Neu starten", "en": "Restart"},
    "diagnose_cancel": {"de": "Abbrechen", "en": "Cancel"},
    "diagnose_cancelled": {"de": "Diagnose abgebrochen.", "en": "Diagnose cancelled."},
    "diagnose_done": {"de": "Fertig.", "en": "Done."},
    "more_info": {"de": "Mehr Infos", "en": "More info"},
    "welcome_dm_failed_log": {
        "de": "DM an {user} fehlgeschlagen (wahrscheinlich DMs deaktiviert).",
        "en": "DM to {user} failed (DMs likely closed).",
    },
    "welcome_fallback_channel": {
        "de": "👋 Willkommen, {mention}! Alle Infos zur Community per DM — oder direkt `/faq`, `/glossar` und `/diagnose` ausprobieren.",
        "en": "👋 Welcome, {mention}! Full community info is in your DMs — or try `/faq`, `/glossary`, and `/diagnose` directly.",
    },
}


def t(key: str, locale: Locale, **kwargs: object) -> str:
    bundle = UI.get(key)
    if bundle is None:
        return key
    return bundle.get(locale, bundle.get(DEFAULT_LOCALE, key)).format(**kwargs)


def resolve_locale(
    pref: Locale | None,
    interaction_locale: str | None = None,
) -> Locale:
    """Pick the content locale for a user.

    Saved per-user preference wins. Otherwise we try to match the user's Discord
    client language (which is per-interaction), and if that's neither de nor en
    we fall back to German — this community is DE-primary.
    """
    if pref in SUPPORTED:
        return pref  # type: ignore[return-value]
    return normalise(interaction_locale)
