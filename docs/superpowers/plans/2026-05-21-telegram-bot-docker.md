# Telegram Bot Docker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Docker-deployable Telegram sender that delivers the generated learner video rotation from VPS disk.

**Architecture:** Keep media generation and Telegram delivery separate. A schedule module computes day-to-episode-mode items, an output resolver maps those items to generated MP4s, a Telegram client uploads files, and a bot service stores sent-day state so repeated runs do not resend by default.

**Tech Stack:** Python 3.11, Typer CLI, httpx for Telegram Bot API, pytest with mocked HTTP clients, Docker Compose.

---

### Task 1: Schedule And Output Resolution

**Files:**
- Create: `src/chinese_media_feeder/schedule.py`
- Test: `tests/test_schedule.py`

- [ ] Write failing tests for days 1-8 rotation, mode 4 aliasing to mode 1, and missing output reporting.
- [ ] Implement schedule item generation and generated-output discovery.
- [ ] Run `python -m pytest tests/test_schedule.py -q`.

### Task 2: Telegram Client And Bot State

**Files:**
- Create: `src/chinese_media_feeder/telegram.py`
- Create: `src/chinese_media_feeder/bot.py`
- Test: `tests/test_telegram.py`
- Test: `tests/test_bot.py`

- [ ] Write failing tests for message/video request construction and non-OK Telegram errors.
- [ ] Write failing tests for state idempotency, force resend, and dry-run behavior.
- [ ] Implement Telegram API client, JSON state store, and send-day service.
- [ ] Run `python -m pytest tests/test_telegram.py tests/test_bot.py -q`.

### Task 3: CLI And Configuration

**Files:**
- Modify: `src/chinese_media_feeder/config.py`
- Modify: `src/chinese_media_feeder/cli.py`
- Test: `tests/test_config.py`
- Test: `tests/test_cli.py`

- [ ] Write failing tests for Telegram env loading and bot CLI commands.
- [ ] Add bot config fields and CLI commands: `schedule preview`, `bot test`, `bot send-day`, `bot run`.
- [ ] Run `python -m pytest tests/test_config.py tests/test_cli.py -q`.

### Task 4: Docker And Documentation

**Files:**
- Modify: `pyproject.toml`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `README.md`

- [ ] Add `httpx` runtime dependency.
- [ ] Update Compose with generator and bot services.
- [ ] Document local and VPS commands.
- [ ] Run full tests and Docker build.

### Task 5: Local And Live Verification

**Files:**
- No code changes expected.

- [ ] Run `python -m pytest -q`.
- [ ] Run schedule preview against current generated media.
- [ ] Run a dry-run bot send for an available day.
- [ ] Run Docker status/preview commands.
- [ ] Send one Telegram test message and one available video using `.env`, without printing secrets.
