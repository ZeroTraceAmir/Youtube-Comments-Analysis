# AGENTS.md

Flat Python 3.13 project managed by `uv`. No package layout, no tests, no CI, no linter/formatter config — verification means running the scripts.

## Commands

```bash
uv sync                                  # install deps
uv run listener.py                       # poll RSS feeds, save new videos to DB
uv run fetcher.py                        # analyze waiting videos (older than 48h), send to Telegram
uv run fetcher.py --url "YOUTUBE_URL"    # analyze one video immediately
uv run database.py                       # print the videos table
```

Run from the project root — scripts use relative paths (`channels.json`, `.env`, `yt-pipeline.db`, `pipeline.log`).

## Runtime prerequisites

- `.env` (copy from `.env.example`): `YOUTUBE_API_KEY`, `OPENCODE_API_KEY` (OpenCode Go/Zen account key), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Optional `PROXY` (e.g. `127.0.0.1:7898`) routes all outbound traffic (both scripts use `requests`) through it — empty means direct connection. Bare `host:port` defaults to the `socks5h://` scheme (PySocks dep); write an explicit scheme to override. `fetcher.py` exits 1 without the four keys; `listener.py` only uses RSS and needs no keys.
- `channels.json` (copy from `channels.json.example`): map of channel/playlist ID → name, with optional per-channel `mode`. Both files and `*.db`/`pipeline.log` are gitignored.
- `yt-pipeline.db` is auto-created SQLite in the CWD; delete the file to reset it.

## Architecture

Two standalone scripts on a cron cycle (see `cron.template`; listener on odd hours, fetcher on even), sharing `database.py` (SQLite, WAL mode):

- `listener.py` → reads RSS feeds for `channels.json` entries, inserts videos with status `waiting` (only the newest 3 per channel; the rest are stored as `skipped`)
- `fetcher.py` → for `waiting` videos older than 48h: fetch comments (YouTube Data API) → analysis via OpenCode Go (OpenAI-compatible endpoint, primary model + cheap fallbacks) → Telegram Bot API `sendMessage` (messages split at 3900 chars)

Per-channel analysis modes (`ideas` / `demographics` / `both`) are read from `channels.json` at fetch time — never stored in the DB. Unknown channel or missing `mode` → `ideas`. Manual runs can override with `--mode`.

Other tunables live in function signatures, not config: batch limit in `save_rss_videos(insert_limit=3)` and wait window in `get_expired_videos(hours_passed=48)` (both in `database.py`).

## Gotchas

- Analysis calls OpenCode Go (`https://opencode.ai/zen/go/v1/chat/completions`). Primary model is `OPENCODE_MODEL` (default `glm-5.3-flash`); fallback chain lives in `OPENCODE_FALLBACK_MODELS` (fetcher.py). When updating the model list, keep the price table in README.md in sync.
- Demographics responses must parse as `{"female_pct", "male_pct", "avg_age"}` — invalid JSON triggers the next fallback model, not a failed video.
- Video status is DB-constrained to `waiting`/`processed`/`skipped`.
- Sentinels `"NETWORK_ERROR"` (analysis result) and `["NETWORK_ERROR"]` (comments list) mean "retry next cycle" — do not mark those videos processed.
- Shorts are intentionally ignored (URL check in `listener.py`; a `UUSH`-prefixed channel ID would yield nothing).
- Installing the cron must run from the project root: `sed "s|TARGET_DIRECTORY|$PWD|g" cron.template | crontab -`

## Style

- 2-space indentation, not PEP 8's 4.
- Log through `utils.log()` with `[LISTENER]`/`[FETCHER]`/`[DATABASE]` prefixes, not bare `print()`.
