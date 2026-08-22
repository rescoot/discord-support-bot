"""First-line answer suggester for the support forum.

Indexes the thread dump (scripts/dump_forum.py) with BM25 and, for a new
question, shows the closest past threads together with the first real human
answer each of them got, plus the FAQ entries the forum tags map to.

    python scripts/suggest.py "AUX leer, Roller wacht nicht auf" --tag Akkuproblem
    python scripts/suggest.py --eval

No new dependencies, no model calls: this is the retrieval half. Feeding the
same hits to an LLM for an actual draft reply is the obvious next step, and the
retrieval quality is what decides whether that draft is any good.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from unubot.content import load_content  # noqa: E402

# Words that carry no signal in a German/English support forum. Product nouns
# like "roller" or "akku" are deliberately kept, they do discriminate here.
_DE_STOP = {
    "aber", "alle", "allem", "allen", "als", "also", "am", "an", "auch", "auf", "aus", "bei",
    "beim", "bin", "bis", "bzw", "da", "dann", "das", "dass", "dem", "den", "der", "des", "die",
    "dies", "diese", "diesem", "diesen", "dieser", "doch", "dort", "du", "durch", "ein", "eine",
    "einem", "einen", "einer", "eines", "er", "es", "etwas", "euch", "fuer", "für", "gar",
    "gegen", "gibt", "habe", "haben", "hat", "hatte", "hier", "ich", "ihm", "ihn", "ihr", "im",
    "immer", "in", "ins", "ist", "ja", "kann", "kein", "keine", "koennen", "können", "leider",
    "mal", "man", "mehr", "mein", "meine", "mich", "mir", "mit", "muss", "nach", "nicht",
    "nichts", "noch", "nun", "nur", "ob", "oder", "ohne", "schon", "sehr", "sein", "seine",
    "sich", "sie", "sind", "so", "soll", "sonst", "über", "uber", "um", "und", "uns", "unter",
    "vom", "von", "vor", "war", "waren", "was", "weil", "weiter", "wenn", "wer", "werden", "wie",
    "wieder", "wir", "wird", "wo", "wurde", "zu", "zum", "zur", "zwei"
}

# English half, kept separate so the two lists stay editable on their own.
_EN_STOP = {
    "a", "about", "after", "all", "and", "any", "are", "as", "at", "be", "been", "but", "by",
    "can", "did", "do", "does", "for", "from", "get", "had", "has", "have", "his", "how", "i",
    "if", "into", "is", "it", "its", "just", "like", "me", "my", "no", "not", "of", "on", "one",
    "only", "or", "out", "some", "still", "that", "the", "their", "them", "then", "there",
    "they", "this", "to", "try", "up", "we", "were", "what", "when", "which", "will", "with",
    "would", "you", "your"
}

STOPWORDS = _DE_STOP | _EN_STOP

_TOKEN_RE = re.compile(r"[a-zA-Z0-9äöüßÄÖÜ]+")
_URL_RE = re.compile(r"https?://\S+")


def tokenize(text: str) -> list[str]:
    text = _URL_RE.sub(" ", text.lower()).replace("ß", "ss")
    return [tok for tok in _TOKEN_RE.findall(text) if len(tok) >= 3 and tok not in STOPWORDS]


@dataclass
class Doc:
    key: str
    title: str
    tags: list[str]
    tokens: list[str]
    payload: dict = field(default_factory=dict)


class BM25:
    """Plain BM25, small enough that a dependency would cost more than it saves."""

    K1 = 1.5
    B = 0.75

    def __init__(self, docs: list[Doc]):
        self.docs = docs
        self.freqs = [Counter(d.tokens) for d in docs]
        self.lengths = [len(d.tokens) for d in docs]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        postings: dict[str, int] = defaultdict(int)
        for f in self.freqs:
            for term in f:
                postings[term] += 1
        n = len(docs)
        self.idf = {
            term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in postings.items()
        }

    def search(self, query: str, limit: int = 5, exclude: str | None = None) -> list[tuple[float, Doc]]:
        q = tokenize(query)
        if not q:
            return []
        scored: list[tuple[float, Doc]] = []
        for i, doc in enumerate(self.docs):
            if exclude is not None and doc.key == exclude:
                continue
            freq = self.freqs[i]
            length = self.lengths[i] or 1
            score = 0.0
            for term in q:
                tf = freq.get(term)
                if not tf:
                    continue
                denom = tf + self.K1 * (1 - self.B + self.B * length / (self.avg_len or 1))
                score += self.idf.get(term, 0.0) * tf * (self.K1 + 1) / denom
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda s: s[0], reverse=True)
        return scored[:limit]


def first_human_answer(thread: dict) -> dict | None:
    """The first reply that isn't the poster themselves and isn't a one-liner.

    That is roughly what a first-line responder would have written, which is
    exactly what we want to suggest for the next post like it.
    """
    owner = thread["messages"][0]["author"]["id"] if thread["messages"] else None
    for msg in thread["messages"][1:]:
        if msg["author"]["bot"] or msg["author"]["id"] == owner:
            continue
        if len(msg["content"].strip()) < 40:
            continue
        return msg
    return None


def load_threads(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"no dump at {path}. Run scripts/dump_forum.py first.")
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def build_thread_index(threads: list[dict]) -> BM25:
    docs = []
    for t in threads:
        starter = t["messages"][0]["content"] if t["messages"] else ""
        tags = [tag["name"] for tag in t["applied_tags"]]
        # The title is what someone types when they are still guessing, so it
        # matches new questions well. Weight it by repeating it.
        text = f"{t['name']} {t['name']} {starter}"
        docs.append(
            Doc(
                key=str(t["id"]),
                title=t["name"],
                tags=tags,
                tokens=tokenize(text),
                payload={"thread": t},
            )
        )
    return BM25(docs)


def build_faq_index(content_dir: Path) -> tuple[BM25, dict]:
    store = load_content(content_dir)
    docs = []
    for entry in store.faq.values():
        text = " ".join(
            [entry.title.get("de", ""), " ".join(entry.aliases), entry.body.get("de", "")]
        )
        docs.append(
            Doc(key=entry.id, title=entry.title.get("de", entry.id), tags=list(entry.tags),
                tokens=tokenize(text))
        )
    return BM25(docs), store


def _quote(text: str, width: int = 3) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()][:width]
    return "\n".join(f"         > {line[:110]}" for line in lines)


def cmd_query(args, threads, thread_index, faq_index, store) -> int:
    query = " ".join(args.query)
    tags = args.tag or []

    faq_ids = store.forum_tags.suggestions_for(tags) if tags else []
    print(f"\n=== Frage ===\n{query}")
    if tags:
        print(f"Tags: {', '.join(tags)}")

    print("\n=== FAQ nach Tag ===")
    if faq_ids:
        for fid in faq_ids:
            print(f"  /faq thema:{fid}  ({store.faq[fid].title.get('de','')})")
    else:
        print("  (keine Zuordnung, siehe content/forum_tags.yaml)")

    print("\n=== FAQ nach Text ===")
    hits = faq_index.search(query, limit=3)
    if not hits:
        print("  (nichts)")
    for score, doc in hits:
        print(f"  {score:5.1f}  /faq thema:{doc.key}  ({doc.title})")

    print("\n=== Ähnliche Threads und ihre erste Antwort ===")
    for score, doc in thread_index.search(query, limit=args.limit):
        thread = doc.payload["thread"]
        answer = first_human_answer(thread)
        print(f"\n  {score:5.1f}  {doc.title}")
        print(f"         [{', '.join(doc.tags) or '-'}]  {len(thread['messages'])} Nachrichten")
        if answer:
            print(f"         erste Antwort von {answer['author']['display_name']}:")
            print(_quote(answer["content"]))
        else:
            print("         (keine verwertbare erste Antwort)")
    print()
    return 0


def cmd_eval(args, threads, thread_index, faq_index, store) -> int:
    """Leave-one-out: does the retrieval find threads about the same thing?

    Tag overlap is a weak proxy, but it is the only label the dump carries, and
    it catches an index that returns noise.
    """
    hits = 0
    considered = 0
    no_answer = 0
    for t in threads:
        tags = {tag["name"] for tag in t["applied_tags"]}
        if not tags or not t["messages"]:
            continue
        considered += 1
        query = f"{t['name']} {t['messages'][0]['content']}"
        top = thread_index.search(query, limit=3, exclude=str(t["id"]))
        if any(tags & set(doc.tags) for _score, doc in top):
            hits += 1
        if first_human_answer(t) is None:
            no_answer += 1
    print(f"threads evaluated:        {considered}")
    print(f"top-3 shares a tag:       {hits} ({hits / considered:.0%})")
    print(f"threads without a usable first answer: {no_answer}")
    answered = [t for t in threads if first_human_answer(t)]
    lengths = [len(first_human_answer(t)["content"]) for t in answered]
    if lengths:
        lengths.sort()
        print(f"first answer length: median {lengths[len(lengths) // 2]} chars, max {lengths[-1]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="*", help="the new question, as free text")
    ap.add_argument("--tag", action="append", help="forum tag on the post (repeatable)")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--dump", type=Path, default=Path("state/support_dump/threads.jsonl"))
    ap.add_argument("--content", type=Path, default=Path("content"))
    ap.add_argument("--eval", action="store_true", help="score the retrieval against the dump")
    args = ap.parse_args()

    if not args.query and not args.eval:
        ap.error("give a question, or --eval")

    threads = load_threads(args.dump)
    thread_index = build_thread_index(threads)
    faq_index, store = build_faq_index(args.content)

    if args.eval:
        return cmd_eval(args, threads, thread_index, faq_index, store)
    return cmd_query(args, threads, thread_index, faq_index, store)


if __name__ == "__main__":
    raise SystemExit(main())
