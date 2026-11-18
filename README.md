<p align="center">
  <img src="images/logo.png" alt="Messenger Analyzer" width="450">
</p>

# Messenger Analyzer

Statistics and charts for your Facebook Messenger conversations, from the
command line. Everything runs locally; nothing is sent over the network.

- Messages per day, month, weekday and hour, overall or per participant
- Response times (overall, per person, per month)
- Words per message, most common words, keyword search
- Message types: text, photos, videos, voice notes, calls, stickers, ...
- Text or JSON reports, and charts saved as PNG/SVG/PDF or shown in a window

Handles conversations with hundreds of thousands of messages in about a second.
Any number of participants works.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/kordoulakis/MessengerAnalyzer.git
cd MessengerAnalyzer
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[plot]"
```

Leave out `[plot]` if you only need text/JSON reports.

## Get your data

1. Go to <https://facebook.com/dyi> (Settings → Your Facebook information → Download your information).
2. Select only **Messages**, format **JSON**, date range **All time**.
3. Unzip the download. Each conversation is a folder containing `message_1.json`,
   `message_2.json`, ...
4. Copy the conversation folders you want into `MessagesSources/` and give them
   short names. That folder is git-ignored, so your chats are never committed.

## Usage

```bash
msganalyzer list                          # conversations found in MessagesSources/
msganalyzer report alex                   # every statistic, as text
msganalyzer report alex --format json -o alex.json
msganalyzer charts                        # list available charts
msganalyzer plot alex monthly --by-participant
msganalyzer plot alex daily --keywords "coffee,beer" -o drinks.png
msganalyzer plot alex responses-monthly --unit hours --max-gap 12h
```

`alex` can be a folder name inside `MessagesSources/` or any path to a
conversation folder. Try it on the bundled sample: `msganalyzer report example`.

Useful options (see `msganalyzer <command> --help` for all):

| Option | Meaning |
|---|---|
| `--tz Europe/Athens` | Timezone for dates and hours (default: your computer's) |
| `--max-gap 6h` | Ignore "responses" that come after a long silence; they are usually new conversations |
| `--keywords a,b` | Count these words (`report`) or only chart messages containing them (`plot daily`) |
| `--by-participant` / `--separate` | One series, or one panel, per participant |
| `-o FILE` | Save instead of printing / opening a window |
| `-v` | Print load and analysis timings |

### As a library

```python
from pathlib import Path
from messenger_analyzer import loaders, analysis as an

conv = loaders.load(Path("MessagesSources/alex")).in_timezone("Europe/Athens")
print(an.messages_per_period(conv.messages, "month", by_sender=True))
print(an.top_words(conv.messages, 20))
```

## Development

```bash
pip install -e . --group dev   # pip >= 25.1
pytest                         # tests
ruff check . && ruff format .  # lint and format
mypy                           # type-check
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the code is organised,
how to add a new chat platform, and benchmark numbers.

## Roadmap

- Instagram and WhatsApp exports
- Web interface

## License

MIT. See [LICENSE](LICENSE).
