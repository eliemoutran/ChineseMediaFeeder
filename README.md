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
BOT_TIMEZONE=Asia/Manila
BOT_START_TIME=07:00
BOT_NUDGE_TIME=14:00
BOT_REMINDER_TIME=22:00
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
cmf bot state
cmf bot reset
cmf bot set-day --day 1
cmf bot set-start --time 07:00 --timezone Asia/Manila
cmf bot set-nudge --time 14:00
cmf bot set-reminder --time 22:00
cmf bot test --with-video
```

The bot rotation is:

- Day N: episode N, Mode 1
- Day N-1: Mode 2
- Day N-2: Mode 3
- Day N-5: Mode 4

`cmf bot send-day` is still available for manual whole-day sends. The long-running bot uses an interactive rolling lesson flow:

- At `BOT_START_TIME`, it starts or resumes the current learner day and sends only the next pending video.
- Each video has a `✅ Watched` button. Tapping it records progress and unlocks the next video.
- At `BOT_NUDGE_TIME`, if the day is incomplete, it sends a light nudge.
- At `BOT_REMINDER_TIME`, if the day is still incomplete, it sends the stronger reminder.
- The bot does not advance to the next learner day until the current day is complete. Use `/skip` or `cmf bot set-day --day N` if you intentionally want to move on.

Telegram commands supported by the long-running bot:

```text
/state
/today
/setstart 07:00
/setnudge 14:00
/setreminder 22:00
/skip
/reset
/help
```

The bot records progress in `media/bot/state.json`. Use `cmf bot reset` to reset back to Day 1.

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
docker compose run --rm bot cmf bot state
docker compose run --rm bot cmf bot reset
docker compose run --rm bot cmf bot set-start --time 07:00 --timezone Asia/Manila
```

To deploy updates on a VPS:

```bash
git pull
docker compose build
docker compose up -d bot
docker compose logs -f bot
```
