# Interactive Daily Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace whole-day Telegram delivery with a rolling daily lesson flow that sends one video at a time, unlocks the next video through a Watched button, and sends configurable 2 PM / 10 PM reminders.

**Architecture:** Keep video generation unchanged. Add a focused interactive bot layer around the existing schedule resolver: state owns active learner-day progress, scheduler decides when checkpoints are due in a configured timezone, Telegram client supports inline buttons and polling updates, and CLI commands expose reset/time/state admin operations.

**Tech Stack:** Python 3.13, Typer, httpx, Telegram Bot API polling, zoneinfo, pytest, Docker Compose.

---

### Task 1: Time and Runtime Config

**Files:**
- Modify: `src/chinese_media_feeder/config.py`
- Modify: `.env.example`
- Modify: `tests/test_config.py`

- [ ] Add tests that `Settings.from_env()` reads `BOT_TIMEZONE`, `BOT_START_TIME`, `BOT_NUDGE_TIME`, and `BOT_REMINDER_TIME`, with defaults `Asia/Manila`, `07:00`, `14:00`, and `22:00`.
- [ ] Verify the tests fail because the settings fields do not exist yet.
- [ ] Add the fields to `Settings` and parse the env variables as strings.
- [ ] Update `.env.example` and the env-template regression test.
- [ ] Run `pytest tests/test_config.py -q` and confirm it passes.

### Task 2: Interactive State Store

**Files:**
- Modify: `src/chinese_media_feeder/bot.py`
- Modify: `tests/test_bot.py`

- [ ] Add tests for the new state shape: empty state, starting an active session, recording watched item indexes, completing a day, skipping a day, storing checkpoint dates, and resetting state.
- [ ] Verify the tests fail because the state methods do not exist.
- [ ] Extend `BotStateStore` with methods for `reset()`, `current_session()`, `start_day(day, total_items, local_date)`, `mark_item_sent(index, message_id)`, `mark_watched(index)`, `complete_active_day()`, `skip_active_day()`, `record_checkpoint(kind, local_date)`, and `checkpoint_sent(kind, local_date)`.
- [ ] Preserve compatibility with existing `sent_days` state where practical by treating `next_day()` as one plus the highest completed or sent day.
- [ ] Run `pytest tests/test_bot.py -q`.

### Task 3: Progressive Lesson Sender

**Files:**
- Modify: `src/chinese_media_feeder/bot.py`
- Modify: `tests/test_bot.py`

- [ ] Add tests that starting a day sends only item 0 with a Watched button, watching item 0 sends item 1, watching the final item sends completion text, duplicate watched callbacks do not send duplicates, `/today` resends the current pending item, and an unfinished day resumes instead of advancing.
- [ ] Verify the tests fail on missing behavior.
- [ ] Add `InteractiveDailySender` that uses `build_day_schedule()` and `resolve_schedule_outputs()` but sends one resolved item at a time.
- [ ] Add callback payloads with compact data such as `watched:<day>:<index>`.
- [ ] Keep the existing `DailySender` for backward-compatible `send-day`, but make `bot run` use the interactive sender.
- [ ] Run `pytest tests/test_bot.py -q`.

### Task 4: Wall-Clock Scheduler

**Files:**
- Create: `src/chinese_media_feeder/bot_scheduler.py`
- Create: `tests/test_bot_scheduler.py`

- [ ] Add tests for checkpoint detection at 7 AM, 2 PM, and 10 PM in `Asia/Manila`, no duplicate checkpoint per local date, late startup after 7 AM starting the day, and unfinished active day resuming at the next 7 AM.
- [ ] Verify the tests fail because the scheduler module does not exist.
- [ ] Implement pure functions for parsing `HH:MM`, getting local date/time, deciding due checkpoints, and computing short sleep seconds until the next poll.
- [ ] Run `pytest tests/test_bot_scheduler.py -q`.

### Task 5: Telegram Inline Buttons and Polling

**Files:**
- Modify: `src/chinese_media_feeder/telegram.py`
- Modify: `tests/test_telegram.py`

- [ ] Add tests that `send_message()` and `send_video()` can include `reply_markup`, `get_updates()` calls `getUpdates` with offset/timeout, and `answer_callback_query()` calls Telegram correctly.
- [ ] Verify tests fail because these methods/args do not exist.
- [ ] Implement optional `reply_markup` support by JSON-encoding it for Bot API requests.
- [ ] Implement `get_updates(offset, timeout)` and `answer_callback_query(callback_query_id, text=None)`.
- [ ] Run `pytest tests/test_telegram.py -q`.

### Task 6: CLI and Bot Loop

**Files:**
- Modify: `src/chinese_media_feeder/cli.py`
- Modify: `tests/test_cli.py`

- [ ] Add tests for `cmf bot state`, `reset`, `set-day`, `set-start`, `set-nudge`, and `set-reminder`.
- [ ] Add tests that `bot run --once --dry-run` processes the due checkpoint without Telegram and exits.
- [ ] Verify tests fail because commands and interactive loop are missing.
- [ ] Implement admin commands.
- [ ] Implement polling loop that alternates between due-checkpoint handling and Telegram update handling.
- [ ] Ensure callback/chat ids are validated against `TELEGRAM_CHAT_ID`.
- [ ] Run `pytest tests/test_cli.py -q`.

### Task 7: Docs and Deployment Notes

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

- [ ] Document the rolling active-day behavior.
- [ ] Document the three configurable times.
- [ ] Document reset/state/time commands.
- [ ] Document VPS update commands: `git pull`, `docker compose build`, `docker compose up -d bot`.

### Task 8: Full Verification and Simulation

**Files:**
- No code files expected.

- [ ] Run focused tests for config, bot, scheduler, telegram, and CLI.
- [ ] Run full suite with `python -m pytest`.
- [ ] Build Docker with `docker compose build`.
- [ ] Simulate key scenarios in tests: fresh day start, watched progression, day completion, incomplete day at 2 PM, incomplete day at 10 PM, next morning resume, skip active day, reset state, custom time config, duplicate callback, unauthorized callback.
- [ ] Commit and push the completed feature.
