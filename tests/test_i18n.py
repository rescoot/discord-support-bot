from unubot.i18n import DEFAULT_LOCALE, normalise, pick, t


def test_default_is_german():
    assert DEFAULT_LOCALE == "de"


def test_normalise_falls_back_to_german_for_unknown():
    assert normalise(None) == "de"
    assert normalise("") == "de"
    assert normalise("fr") == "de"
    assert normalise("nl-NL") == "de"


def test_normalise_detects_english_variants():
    assert normalise("en") == "en"
    assert normalise("en-US") == "en"
    assert normalise("en-GB") == "en"
    assert normalise("EN") == "en"


def test_pick_prefers_requested_locale():
    assert pick({"de": "DE", "en": "EN"}, "en") == "EN"
    assert pick({"de": "DE", "en": "EN"}, "de") == "DE"


def test_pick_falls_back_when_missing():
    assert pick({"de": "DE"}, "en") == "DE"
    assert pick({}, "en") == ""
    assert pick(None, "de") == ""
    assert pick("plain", "en") == "plain"


def test_t_formats_with_kwargs():
    msg = t("reload_ok", "de", faq=3, glossary=4, diagnose=2)
    assert "3" in msg and "4" in msg and "2" in msg
