<p align="center">
  <img src="images/logo.png" alt="Nostos" width="450">
</p>

# Nostos

*νόστος (Greek): homecoming, the root of "nostalgia".*

Nostos turns your chat history into statistics and interactive charts, so you can
look back on your conversations: who talks most, when you talk, how fast you
reply, how it all changed over the years.

It runs entirely on your computer. Your messages are never uploaded anywhere.

![Nostos dashboard](images/dashboard.png)

**Supported today:** Facebook Messenger and Instagram (JSON exports) and WhatsApp
("Export chat" text files, from Android or iPhone).

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/kordoulakis/MessengerAnalyzer.git nostos
cd nostos
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
nostos dashboard example           # opens a dashboard of the bundled sample chat
```

Then [download your own chats](#get-your-chats) and run `nostos dashboard <name>`.

## Get your chats

Copy each conversation into the `chats/` folder of this project. `chats/` is
ignored by git, so your chats are never committed by accident. `nostos list` shows
what it finds there.

### Messenger

1. On Facebook, open **Download your information**: <https://www.facebook.com/dyi>
   (or Settings → Accounts Center → Your information and permissions → Download your
   information). Facebook moves these menus around from time to time.
2. Choose **Messages** only, format **JSON** (not HTML), date range **All time**, and
   request the download. Facebook emails you when it's ready.
3. Unzip it and find the `inbox` folder (usually `your_facebook_activity/messages/inbox/`,
   or `messages/inbox/` in older exports). It has one folder per conversation, named
   like `alexsmith_123456789`, each containing `message_1.json`, `message_2.json`, ...
4. Copy the conversations you want into `chats/` and rename them to something
   short, e.g. `chats/alex/`.

> Chats that use end-to-end encryption (the default for new Messenger chats since
> late 2023) may be missing from this export or contain only older messages.

### Instagram

1. In the Instagram app or website, open Accounts Center → Your information and
   permissions → **Download your information**, and request a download of your
   **Messages** in format **JSON**, date range **All time**.
2. Unzip it and find `your_instagram_activity/messages/inbox/`. As with Messenger,
   each conversation is a folder containing `message_1.json`, ...
3. Copy the conversations you want into `chats/`, e.g. `chats/alex-insta/`.

Instagram and Messenger exports look the same. Nostos tells them apart
automatically; if it guesses wrong, add `--platform instagram` or `--platform messenger`.

### WhatsApp

1. Open the chat on your phone.
   - **Android:** ⋮ → More → **Export chat** → **Without media**. You get
     `WhatsApp Chat with Alex.txt`.
   - **iPhone:** tap the contact's name → **Export Chat** → **Without Media**. You get
     `WhatsApp Chat - Alex.zip`; unzip it to get a folder containing `_chat.txt`.
2. Copy the `.txt` file, or the unzipped folder, into `chats/`.

WhatsApp writes times in your phone's local time, without a timezone. Nostos reads
them in your computer's timezone; if the phone was set to a different one, pass it
with `--tz`. Dates in any format work (day or month first, 12- or 24-hour clock).
Photos, calls and deleted messages are recognised when the phone's language is
English; in other languages they count as text messages.

## Usage

```bash
nostos list                              # conversations in chats/
nostos dashboard alex                    # all charts and headline numbers on one page
nostos report alex                       # every statistic as text
nostos report alex --format json -o alex.json
nostos charts                            # list the available charts
nostos plot alex monthly --by-participant
nostos plot alex activity --keywords "coffee,beer"
nostos plot alex rhythm -o rhythm.png    # static image instead of an interactive page
```

`alex` is the name of a folder (or WhatsApp `.txt` file) inside `chats/`. You can also
pass any path to a conversation folder or chat file, e.g.
`nostos dashboard ~/Downloads/inbox/alexsmith_123456789` or
`nostos report "chats/WhatsApp Chat with Alex.txt"`.

**Where output goes:**

| Command | Writes | Then |
|---|---|---|
| `nostos dashboard alex` | `alex-dashboard.html` in the current folder | opens it in your browser |
| `nostos plot alex monthly` | `alex-monthly.html` in the current folder | opens it in your browser |
| `nostos report alex` | nothing; prints to the terminal | |
| any of them with `-o FILE` | `FILE` | doesn't open a browser (add `--open` to) |

For `plot`, an `-o` ending in `.png`, `.svg` or `.pdf` saves a static image instead.
That needs the export extra: `pip install -e ".[export]"`.

The HTML pages are single, self-contained files: open them by double-clicking, no
server needed. They follow your system's light or dark mode and have a toggle in the
top-right corner. Hover over any chart for exact values, drag to zoom, double-click
to reset, and open **Data table** under a chart to see its numbers.

### Charts

| Name | Shows |
|---|---|
| `activity` | Messages per day with a rolling average |
| `monthly` | Messages per month; `--by-participant` stacks them by person |
| `share` | Each person's share of the conversation, month by month |
| `rhythm` | Heatmap of when you talk: weekday × hour |
| `participants` | Total messages per person |
| `response-times` | How fast people reply: share of replies under 1 min, 1–5 min, ... |
| `response-trend` | Median reply time, month by month |
| `words` | Average words per message, month by month |
| `kinds` | Message types: text, photos, videos, voice notes, calls, stickers, ... |
| `top-words` | Most used words |

### Options

| Option | Meaning |
|---|---|
| `--by-participant` | One line or bar per person (up to 8; quieter people are grouped as "Other") |
| `--keywords a,b` | `report`: count these words. `plot activity`: only messages containing them |
| `--max-gap 6h` | Ignore replies that come after a long silence; those are usually a new conversation, not a reply |
| `--tz Europe/Athens` | Timezone for dates and hours (default: your computer's). WhatsApp times are also read in it |
| `--platform whatsapp` | Export format, if detection guesses wrong: `messenger`, `instagram` or `whatsapp` |
| `--window 7` | Days in the `activity` rolling average (default: 30) |
| `--unit hours` | Unit for reply times in charts: `seconds`, `minutes` (default) or `hours` |
| `--top 50` | Number of words in `top-words` (default: 20) |
| `--theme dark` | Force a theme: `auto` (default, follows the system), `light` or `dark` |
| `-v` | Show how long loading and analysis took |

`nostos <command> --help` lists every option.

## Privacy

- Nostos reads your export from disk and writes results to disk. It never connects
  to the internet, and the test suite fails if anything tries to.
- Dashboards and charts embed everything they need (which is why a page is about
  5 MB), so they open offline and load nothing from anywhere.
- Generated pages and reports contain names, word lists and activity patterns.
  Treat them as private as the chat itself before sharing them.

## Troubleshooting

**"No chat export found" or "is not a folder or file"**: point Nostos at a single
conversation: for Messenger and Instagram the folder that contains `message_1.json`,
for WhatsApp the `.txt` file or the unzipped folder containing it. Not a zip and not
the `inbox` folder. If the folder has `message_1.html` instead, the export was made in
HTML format: request it again as JSON.

**Hours or days look shifted**: pass your timezone, e.g. `--tz Europe/Athens`. For
WhatsApp, use the timezone the phone was set to.

**Image export fails**: install the export extra (`pip install -e ".[export]"`) and
run `plotly_get_chrome` once so it can find a browser to render with.

**Garbled characters like `Ã©` or `Î“`**: Messenger and Instagram exports mangle every
non-English character, and Nostos repairs this automatically for every language and
for emoji.
If you still see garbled text, please open an issue.

## Use it from Python

```python
from pathlib import Path

from nostos import analysis as an
from nostos import loaders

# timezone= is only used for WhatsApp, whose times have no timezone of their own.
conv = loaders.load(Path("chats/alex"), timezone="Europe/Athens").in_timezone("Europe/Athens")
print(an.messages_per_sender(conv.messages))
print(an.messages_per_period(conv.messages, "month", by_sender=True))
print(an.top_words(conv.messages, 20))
```

Every analysis function takes the messages table and returns a
[Polars](https://pola.rs) DataFrame or a number.

## Development

```bash
pip install -e . --group dev     # needs pip 25.1 or newer
pytest                           # tests
ruff check . && ruff format .    # lint and format
mypy                             # type-check
```

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains how the code is organised, how
to add a new chat platform, and performance numbers. `benchmarks/generate_sample.py`
creates realistic fake chats of any size for testing.

## Roadmap

- Messenger's separate export of end-to-end encrypted chats
- Media, call and system messages in WhatsApp exports from phones not set to English
- A web app

## License

MIT. See [LICENSE](LICENSE).
