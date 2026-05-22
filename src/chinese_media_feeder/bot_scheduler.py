from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class BotScheduleConfig:
    timezone_name: str
    start_time: str
    nudge_time: str
    reminder_time: str


@dataclass(frozen=True)
class DueCheckpoint:
    kind: str
    local_date: str


def parse_hhmm(value: str) -> time:
    try:
        hour_text, minute_text = value.split(":", maxsplit=1)
        parsed = time(hour=int(hour_text), minute=int(minute_text))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected HH:MM time, got {value!r}") from exc
    return parsed


def local_date_string(now: datetime, timezone_name: str) -> str:
    return now.astimezone(_timezone(timezone_name)).date().isoformat()


def due_checkpoints(
    now: datetime,
    config: BotScheduleConfig,
    already_sent: Callable[[str, str], bool],
) -> list[DueCheckpoint]:
    local_now = now.astimezone(_timezone(config.timezone_name))
    local_date = local_now.date().isoformat()
    checkpoints = [
        ("start", parse_hhmm(config.start_time)),
        ("nudge", parse_hhmm(config.nudge_time)),
        ("reminder", parse_hhmm(config.reminder_time)),
    ]
    due: list[DueCheckpoint] = []
    for kind, checkpoint_time in checkpoints:
        if local_now.time() < checkpoint_time:
            continue
        if already_sent(kind, local_date):
            continue
        due.append(DueCheckpoint(kind=kind, local_date=local_date))
    return due


def _timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == "Asia/Manila":
            return timezone(timedelta(hours=8), name="Asia/Manila")
        raise
