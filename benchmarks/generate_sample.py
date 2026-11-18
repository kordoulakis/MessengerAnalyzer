"""Write a synthetic Messenger export for benchmarking.

    python benchmarks/generate_sample.py OUT_DIR --messages 300000 --participants 2

Mirrors the real format: newest messages first, 10,000 per ``message_N.json``,
and every non-ASCII character mangled the way Messenger does it.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

WORDS = [
    "hey",
    "hello",
    "yes",
    "no",
    "maybe",
    "lol",
    "ok",
    "sure",
    "tomorrow",
    "today",
    "tonight",
    "coffee",
    "work",
    "home",
    "καλημέρα",
    "τι",
    "κάνεις",
    "ναι",
    "όχι",
    "😂",
    "❤️",
    "👍",
    "haha",
    "what",
    "why",
    "when",
    "where",
    "who",
    "how",
]
KINDS = ["photos", "videos", "audio_files", "share", "gifs", "sticker"]
PER_FILE = 10_000


def mangle(text: str) -> str:
    return text.encode("utf-8").decode("latin-1")


def generate(out: Path, messages: int, participants: int, seed: int = 0) -> None:
    rng = random.Random(seed)
    names = [
        mangle(n) for n in ["Ana", "Βασίλης", "Chris", "Δήμητρα", "Eve", "Fotis"][:participants]
    ]
    ts = 1_420_070_400_000  # 2015-01-01
    rows = []
    sender = 0
    for _ in range(messages):
        ts += int(rng.expovariate(1 / 600_000))  # ~10 minutes apart on average
        if rng.random() < 0.4:
            sender = rng.randrange(participants)
        message: dict[str, object] = {"sender_name": names[sender], "timestamp_ms": ts}
        if rng.random() < 0.9:
            text = " ".join(rng.choices(WORDS, k=rng.randint(1, 15)))
            message["content"] = mangle(text)
        else:
            message[rng.choice(KINDS)] = [{"uri": "x"}]
        rows.append(message)
    rows.reverse()
    out.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(rows), PER_FILE):
        doc = {
            "participants": [{"name": n} for n in names],
            "messages": rows[i : i + PER_FILE],
            "title": names[-1],
            "thread_type": "Regular",
        }
        (out / f"message_{i // PER_FILE + 1}.json").write_text(json.dumps(doc))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--messages", type=int, default=300_000)
    parser.add_argument("--participants", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    generate(args.out, args.messages, args.participants, args.seed)
