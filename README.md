# yt-idea-bot

Automated tool that monitors YouTube channels via RSS, saves new videos metadata, waits 48 hours, reads the comments and sends the results to Telegram. Depending on the channel, it can extract the content ideas from the comments (using AI models through OpenCode Go), estimate the demographics of the commenters (female/male percentage and guessed average age), or both.

How the pipeline works:

```
┌─────────┐    every 2h     ┌──────────────────────────┐
│ listener │ ─────────────► │ new videos saved as WAITING │
└─────────┘                 └──────────────────────────┘
                                      │ after 48 hours
┌────────┐    every 2h          ┌─────▼───────────────────────────┐
│ fetcher │ ───────────────────► │ comments → AI analysis → Telegram │
└────────┘                      └─────────────────────────────────┘
```

The 48 hour wait is intentional: it gives the comments time to accumulate before analyzing them.

---

## Requirements

Before starting, make sure you have:

- A Linux machine (or any machine with `cron`) that stays on — this runs unattended.
- [Python 3.13+](https://www.python.org/) and [`uv`](https://docs.astral.sh/uv/) installed.
- A YouTube Data API key (free, from Google Cloud).
- An OpenCode Go subscription ($10/month) for the AI analysis.
- A Telegram bot token and a chat ID to receive the results.

The next sections explain where to get each key.

---

## Setup guide

### Step 1 — Install

Install `uv` (if you don't have it):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install the Python dependencies from the project root:

```bash
uv sync
```

### Step 2 — Get a YouTube API key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a project (or pick an existing one).
2. Open **APIs & Services → Library**, search for **YouTube Data API v3** and click **Enable**.
3. Open **APIs & Services → Credentials**, click **Create credentials → API key** and copy it.

The free quota is enough for this bot: 10,000 units/day, and each page of 100 comments costs 1 unit (a typical video with 500 comments uses ~5 units).

### Step 3 — Get an OpenCode API key

The comment analysis runs on [OpenCode Go](https://opencode.ai/docs/go/), a low cost subscription that gives access to a curated set of open models through an OpenAI-compatible API.

1. Sign in at [opencode.ai/auth](https://opencode.ai/auth).
2. Subscribe to **OpenCode Go** ($10/month).
3. Copy your API key.

### Step 4 — Create the Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram and send `/newbot`. Follow the steps and copy the **bot token**.
2. Get the **chat ID** where the results should be delivered: send any message to your new bot, then open this URL in a browser (replace `<TOKEN>` with the bot token):

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

   Find `"chat":{"id": 123456789,...}` in the response and copy that number. For a group chat, add the bot to the group first; group IDs are negative numbers.
3. Send at least one message to the bot from that chat (this unlocks the conversation — bots can't message users first).

### Step 5 — Configure the project

Create your local config files from the examples:

```bash
cp .env.example .env
cp channels.json.example channels.json
```

Open `.env` and fill in the four values from the previous steps:

```
YOUTUBE_API_KEY="..."
OPENCODE_API_KEY="..."
TELEGRAM_BOT_TOKEN="..."
TELEGRAM_CHAT_ID="..."
```

Optionally, set `OPENCODE_MODEL` to change the primary AI model (default: `glm-5.3-flash`).

#### Optional proxy

If your machine needs a proxy to reach the internet (for example, a local Clash/V2Ray SOCKS port), set `PROXY` in `.env`:

```
PROXY="127.0.0.1:7898"
```

All outbound traffic (YouTube API, OpenCode Go, Telegram and the RSS feeds) goes through it. Leave it empty (or remove the line) to connect directly.

The `socks5h://` scheme is assumed when not included in the value (the proxy also resolves domain names — the usual setup for Clash/V2Ray). If your proxy speaks plain HTTP instead, write the scheme explicitly: `PROXY="http://127.0.0.1:7898"`. Both scripts log `Using proxy [...]` at startup when it is active.

### Step 6 — Add channels to monitor

Open `channels.json` and add one entry per channel: the feed ID, a name (used in the messages), and the analysis mode:

```json
{
  "UCLFxxxxxxxxxxxxxxxxxxx": {
    "channel_name": "Some Channel",
    "mode": "ideas"
  },
  "UCLFyyyyyyyyyyyyyyyyyyy": {
    "channel_name": "Other Channel",
    "mode": "demographics"
  }
}
```

The channel ID prefix changes what the feed contains:

| Prefix | Feed Content          |
|--------|-----------------------|
|  UC    | Default channel feed  |
|  UU    | All uploads           |
|  UULF  | Long-form videos only |
|  UUSH  | Shorts only           |
|  UULV  | Live streams only     |

To get a channel's ID: open the channel page, check the URL (`youtube.com/channel/UC...`) or the source of the page (`"externalId":"UC..."`), then swap the prefix as needed. The `UUSH` prefix is pointless here because the bot ignores Shorts.

#### Analysis modes

The `mode` field controls what the bot does with each channel's comments:

| Mode           | What it sends to Telegram |
|----------------|--------------------------|
| `ideas` (default) | Content ideas extracted from the comments, plus overall feedback about the video |
| `demographics` | Only the estimated demographics: female/male percentage and guessed average age of the commenters, with the channel name and video title written beside the numbers |
| `both`         | The ideas analysis followed by the demographics |

Demographics output example:

```
https://youtu.be/VIDEO_ID
Channel: Some Channel
Video: Video Title
Female: 62% | Male: 38%
Guessed average age: ~24 years
```

The mode is read from `channels.json` when the video is processed, so you can change it at any time without touching the database. Omitting the field is the same as using `ideas`.

### Step 7 — Try it

Run the listener once and check that videos appear in the database:

```bash
uv run listener.py
uv run database.py
```

New videos are saved with status `WAITING`. Then force the analysis of any video immediately (without waiting 48 hours) and check that the result arrives in Telegram:

```bash
uv run fetcher.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

If it works, you are ready to automate it.

---

## Automation (Cron)

To install the automated schedule into your system `crontab`, run this command from the project root:

**IT MUST BE FROM THE PROJECT FOLDER WHERE THE `.py` FILES ARE, OTHERWISE IT WON'T WORK**

```bash
sed "s|TARGET_DIRECTORY|$PWD|g" cron.template | crontab -
```

This will configure it run `listener.py` every 2h on the odd hours (01, 03, 05...) and run `fetcher.py` every 2h on the even hours (02, 04, 06...).

This means that every 2h it will get the new videos released in the RSS feed and every 2h it will try to analyze the contents and send it to Telegram (for expired videos).

Example:
```
├── 01:00 - listener
├── 02:00 - fetcher
├── 03:00 - listener
├── 04:00 - fetcher
├── 05:00 - listener
├── 06:00 - fetcher
...
```

A `pipeline.log` file will be created with the last 1000 entries of the log. You can check it for errors.

To remove the automation, run `crontab -e` and delete the two lines.

---

## Daily usage

| Command | What it does |
|---------|--------------|
| `uv run listener.py` | Check the RSS feeds and save new videos (no API keys needed) |
| `uv run fetcher.py` | Analyze all videos that have been waiting 48h+ and send the results to Telegram |
| `uv run fetcher.py --url "YOUTUBE_URL"` | Analyze one specific video immediately |
| `uv run fetcher.py --url "YOUTUBE_URL" --mode demographics` | Same, forcing a mode (`ideas`, `demographics` or `both`) |
| `uv run database.py` | Print the videos table |

Notes on the manual run:

* Useful for old videos or channels that you don't want to add to the monitoring list.
* The mode is taken from the video channel's `mode` in `channels.json`, or `ideas` if the channel is not in the list.
* Logs go to the terminal.
* The video gets marked as `PROCESSED` in the database, so it won't be processed again.

---

## Tuning

Everything lives in `.env` / `channels.json`, except two numbers defined in code:

* **Videos per cycle** — in `save_rss_videos()` (`database.py`, `insert_limit=3`): only the 3 newest videos per channel are marked as `WAITING` per listener cycle; the rest are stored as `SKIPPED`.
* **Wait window** — in `get_expired_videos()` (`database.py`, `hours_passed=48`): how long a video waits before its comments get analyzed.

### AI models

The primary model is `glm-5.3-flash` (the cheapest on Go). If a request fails, it falls back to the next model on the list until one completes the task. The order is based on price and usage limits:

 | Model               | Input $/1M | Output $/1M |
 |---------------------|------------|-------------|
 | glm-5.3-flash       | 0.15       | 0.50        |
 | mimo-v2.5           | 0.14       | 0.28        |
 | deepseek-v4-flash   | 0.22–0.44  | 0.66–1.32   |
 | qwen3.8-flash       | 0.15       | 0.47        |

`deepseek-v4-flash` peak hours are 01:00–04:00 and 06:00–10:00 UTC; outside those hours it uses the cheaper off-peak price.

You can replace the primary model with any other Go model by setting `OPENCODE_MODEL` in `.env`.

---

## Troubleshooting

* **Check the logs** — with cron, look at `pipeline.log`; with manual runs, read the terminal output.
* **A video stays in `WAITING` forever** — the analysis or the network failed on every attempt (every model failed). It will be retried automatically on the next cycle; if it never succeeds, check the log for the error.
* **A video is `SKIPPED`** — it had no comments, comments were disabled, or it was outside the newest 3 of its channel when saved.
* **Nothing arrives in Telegram** — run `uv run fetcher.py --url "..."` manually and read the log. `Telegram http client error: Unauthorized` means the bot token is wrong; `chat not found` means the chat ID is wrong or you never sent a message to the bot from that chat.
* **Message lost** — if a message can't be delivered to Telegram after all retries, it is saved to the `failed-messages/` folder instead of being thrown away.
* **Connection errors everywhere** — if `PROXY` is set in `.env`, make sure the proxy is actually running on that address/port. It must be a SOCKS5 proxy (the default assumed scheme is `socks5h://`); for an HTTP proxy write `PROXY="http://..."`. Clear the setting to connect directly.
* **Start over** — the pipeline creates an SQLite database named `yt-pipeline.db`. Delete that file to reset everything.

---

## Project files

* **`listener.py`**: Gets new videos from the YouTube RSS feed and saves them to the database.
* **`fetcher.py`**: Fetches comments for expired videos, analyzes them with OpenCode Go (ideas, demographics or both), and sends the results to Telegram.
* **`database.py`**: Manages the SQLite database.
* **`utils.py`**: Helper utilities.
* **`channels.json.example`**: Example file for the channel list that will be monitored.
* **`.env.example`**: Example file for the environment variables needed.
* **`pyproject.toml`**: Python project configuration and dependencies.
* **`cron.template`**: Automation template for cron.

## Credits

Shoutout to [@perceptreneur](https://github.com/perceptreneur), who originally built this project — this repo is based on their [yt-idea-bot](https://github.com/perceptreneur/yt-idea-bot), with my own modifications on top.

## License
MIT
