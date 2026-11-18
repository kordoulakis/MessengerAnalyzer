"""Write a synthetic but realistic Messenger export, for benchmarks and demos.

    python benchmarks/generate_sample.py OUT_DIR --messages 300000 --participants 3

Mirrors the real format: newest messages first, 10,000 per ``message_N.json``,
and every non-ASCII character mangled the way Messenger does it. The chat has
the shape of a real one: people sleep at night and talk more in the evening,
weekends differ from weekdays, busy and quiet phases come and go over the
years, messages arrive in bursts, and each person has their own habits.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORDS = (  # noqa: SIM905 - a word list reads better as one string
    "hey hello yes no maybe lol ok sure tomorrow today tonight coffee work home dinner "
    "movie game later now soon what why when where who how really nice cool thanks "
    "καλημέρα τι κάνεις ναι όχι εντάξει αύριο σήμερα φαγητό δουλειά σπίτι "
    "haha 😂 ❤️ 👍 🎉"
).split()
NAMES = ["Ana", "Βασίλης", "Chris", "Δήμητρα", "Eve", "Fotis", "Γιώργος", "Hana", "Ilias", "Jo"]
MEDIA = ["photos", "videos", "audio_files", "share", "gifs", "sticker"]
PER_FILE = 10_000

# Relative activity by hour of day (local time): quiet nights, lunch and evening peaks.
HOURLY = [3, 1.5, 0.8, 0.4, 0.3, 0.3, 0.6, 1.5, 3, 4, 4.5, 5, 6, 6, 5, 5, 5.5, 6, 7, 8, 9, 10, 9, 6]
# Monday..Sunday
WEEKLY = [0.9, 0.95, 1.0, 1.0, 1.15, 1.3, 1.1]


def mangle(text: str) -> str:
    return text.encode("utf-8").decode("latin-1")


def _intensity(day: int, rng: random.Random, phases: list[tuple[int, float]]) -> float:
    """Long-term shape: a slow seasonal wave times the current phase of the relationship."""
    phase = next(level for start, level in reversed(phases) if day >= start)
    seasonal = 1 + 0.25 * math.sin(2 * math.pi * day / 365)
    return max(phase * seasonal * rng.lognormvariate(0, 0.45), 0.0)


def generate(out: Path, messages: int, participants: int, seed: int = 0) -> None:
    rng = random.Random(seed)
    names = NAMES[:participants]
    talkativeness = [rng.uniform(0.6, 1.4) for _ in names]
    verbosity = [rng.uniform(4, 12) for _ in names]
    days = 6 * 365
    start = datetime(2019, 1, 1, tzinfo=timezone.utc)
    phases = [(0, 1.0)]
    while phases[-1][0] < days:
        phases.append((phases[-1][0] + rng.randint(60, 300), rng.choice([0.3, 0.6, 1.0, 1.5, 2.2])))

    weights = [
        _intensity(d, rng, phases) * WEEKLY[(start + timedelta(d)).weekday()] for d in range(days)
    ]
    per_day = [messages * w / sum(weights) for w in weights]

    rows: list[dict[str, object]] = []
    for day, expected in enumerate(per_day):
        remaining = round(expected)
        while remaining > 0:
            # A conversation session: a burst of messages starting at a likely hour.
            hour = rng.choices(range(24), weights=HOURLY)[0]
            ts = start + timedelta(days=day, hours=hour, minutes=rng.uniform(0, 59))
            sender = rng.choices(range(len(names)), weights=talkativeness)[0]
            for _ in range(min(remaining, max(1, int(rng.expovariate(1 / 25))))):
                if rng.random() < 0.45:  # someone else replies
                    others = [i for i in range(len(names)) if i != sender]
                    sender = rng.choices(others, weights=[talkativeness[i] for i in others])[0]
                    ts += timedelta(seconds=rng.lognormvariate(4.0, 1.3))
                else:
                    ts += timedelta(seconds=rng.lognormvariate(2.5, 1.0))
                message: dict[str, object] = {
                    "sender_name": mangle(names[sender]),
                    "timestamp_ms": int(ts.timestamp() * 1000),
                }
                if rng.random() < 0.9:
                    k = max(1, int(rng.expovariate(1 / verbosity[sender])))
                    message["content"] = mangle(" ".join(rng.choices(WORDS, k=k)))
                else:
                    message[rng.choice(MEDIA)] = [{"uri": "x"}]
                rows.append(message)
                remaining -= 1

    rows.sort(key=lambda m: m["timestamp_ms"], reverse=True)  # type: ignore[arg-type,return-value]
    out.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(rows), PER_FILE):
        doc = {
            "participants": [{"name": mangle(n)} for n in names],
            "messages": rows[i : i + PER_FILE],
            "title": mangle(", ".join(names[1:]) if len(names) > 2 else names[-1]),
            "thread_type": "Regular" if len(names) == 2 else "RegularGroup",
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
