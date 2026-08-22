from __future__ import annotations

from pathlib import Path

from unubot.content import load_content, reflow

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def test_wrapped_prose_becomes_one_paragraph():
    src = "Typische Reparaturberichte lauten schlicht\n„AUX getauscht, startet einwandfrei\"."
    assert reflow(src) == 'Typische Reparaturberichte lauten schlicht „AUX getauscht, startet einwandfrei".'


def test_blank_lines_still_separate_paragraphs():
    assert reflow("eins\nzwei\n\ndrei") == "eins zwei\n\ndrei"


def test_list_items_keep_their_own_line_and_absorb_continuations():
    src = "• erster Punkt der\n  weitergeht\n• zweiter Punkt\n1. nummeriert\n   auch weitergehend"
    assert reflow(src) == "• erster Punkt der weitergeht\n• zweiter Punkt\n1. nummeriert auch weitergehend"


def test_bold_heading_does_not_swallow_the_paragraph_under_it():
    src = "**Ersatz:**\n12V-Bleibatterie in\nkompakter Bauform."
    assert reflow(src) == "**Ersatz:**\n12V-Bleibatterie in kompakter Bauform."


def test_bold_run_inside_a_sentence_is_not_treated_as_a_heading():
    src = "Die **12V-AUX-Bleibatterie** ist der\nhäufigste Defekt."
    assert reflow(src) == "Die **12V-AUX-Bleibatterie** ist der häufigste Defekt."


def test_fenced_code_survives_verbatim():
    src = "vorher\n```\nlsc keycard list\nlsc keycard add <uid>\n```\nnachher hier\nund da"
    assert reflow(src) == "vorher\n```\nlsc keycard list\nlsc keycard add <uid>\n```\nnachher hier und da"


def test_real_content_has_no_mid_sentence_breaks_left():
    store = load_content(CONTENT_DIR)
    for entry in {**store.faq, **store.glossary}.values():
        for locale, body in entry.body.items():
            in_code = False
            lines = body.splitlines()
            for i, line in enumerate(lines[:-1]):
                if line.strip().startswith("```"):
                    in_code = not in_code
                if in_code or not line.strip():
                    continue
                nxt = lines[i + 1].strip()
                # a line ending mid-sentence followed by more prose is exactly
                # the hard wrap we are folding away
                assert not (
                    line.rstrip().endswith(",") and nxt and nxt[0].islower()
                ), f"{entry.id} [{locale}]: line {i} still wraps mid-sentence"
