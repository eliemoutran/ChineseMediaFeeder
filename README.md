# ChineseMediaFeeder

V1 generates Mandarin learner MP4 variants from local episode files and can send the daily rotation through Telegram.

- Mode 1: no subtitles
- Mode 2: pinyin subtitles
- Mode 3: alternating pinyin and English subtitles
- Mode 4: callback test, sent as the Mode 1 no-sub video with a Mode 4 caption

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Create `.env` and set:

```bash
OPENAI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Optional overrides:

```bash
MEDIA_INPUT_DIR=media/input
MEDIA_WORK_DIR=media/work
MEDIA_OUTPUT_DIR=media/output
MEDIA_MANIFEST_PATH=media/manifest.json
BOT_STATE_PATH=media/bot/state.json
BOT_INTERVAL_SECONDS=86400
```

Transcription runs two OpenAI passes:

- `whisper-1` writes the timing transcript used for subtitle cue start/end times.
- `OPENAI_TRANSCRIBE_MODEL` adds diarized speaker context. Its text/timing is saved for QA, but it does not override the timing transcript.

## Commands

```bash
cmf scan
cmf process media/input/episode-001.mp4
cmf process-all
cmf status
cmf schedule preview --day 6
cmf bot send-day --day 1 --dry-run
cmf bot send-day --day 1
cmf bot test --with-video
```

The bot rotation is:

- Day N: episode N, Mode 1
- Day N-1: Mode 2
- Day N-2: Mode 3
- Day N-5: Mode 4

The bot records sent days in `media/bot/state.json`. Use `--force` on `cmf bot send-day` only when you intentionally want to resend a day.

## Docker

Build and generate videos:

```bash
docker compose build
docker compose run --rm generator
```

Run the Telegram sender as a long-running service:

```bash
docker compose up -d bot
```

Useful checks:

```bash
docker compose run --rm bot cmf status
docker compose run --rm bot cmf schedule preview --day 1
docker compose run --rm bot cmf bot send-day --day 1 --dry-run
```
