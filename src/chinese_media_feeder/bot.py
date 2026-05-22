from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from chinese_media_feeder.schedule import ResolvedScheduleItem, build_day_schedule, resolve_schedule_outputs


class TelegramSender(Protocol):
    def send_message(self, chat_id: str, text: str, reply_markup: dict[str, Any] | None = None) -> dict: ...

    def send_video(
        self,
        chat_id: str,
        video_path: Path,
        caption: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict: ...


@dataclass(frozen=True)
class SendResult:
    day: int
    sent: bool
    message_ids: list[int]
    skipped_reason: str | None = None


class BotStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return _default_state()
        return _normalize_state(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def was_sent(self, day: int) -> bool:
        return str(day) in self.load()["sent_days"]

    def next_day(self) -> int:
        data = self.load()
        if data.get("active_session") is not None:
            return int(data["active_session"]["day"])
        days = [int(day) for day in data.get("sent_days", {})]
        days.extend(int(day) for day in data.get("completed_days", {}))
        configured_next = data.get("next_day")
        if configured_next is not None:
            days.append(int(configured_next) - 1)
        return max(days, default=0) + 1

    def record_sent(self, day: int, message_ids: list[int]) -> None:
        data = self.load()
        data["sent_days"][str(day)] = {
            "message_ids": message_ids,
            "sent_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        self.save(data)

    def reset(self) -> None:
        self.save(_default_state())

    def current_session(self) -> dict | None:
        return self.load().get("active_session")

    def start_day(self, day: int, total_items: int, local_date: str) -> None:
        data = self.load()
        data["active_session"] = {
            "day": day,
            "status": "in_progress",
            "cursor": 0,
            "total_items": total_items,
            "started_local_date": local_date,
            "watched_items": [],
            "sent_items": {},
        }
        data["next_day"] = day
        self.save(data)

    def set_next_day(self, day: int) -> None:
        data = self.load()
        data["active_session"] = None
        data["completed_days"] = {
            key: value for key, value in data.get("completed_days", {}).items() if int(key) < day
        }
        data["sent_days"] = {
            key: value for key, value in data.get("sent_days", {}).items() if int(key) < day
        }
        data["next_day"] = day
        self.save(data)

    def mark_item_sent(self, index: int, message_id: int) -> None:
        data = self.load()
        session = _require_session(data)
        session["sent_items"][str(index)] = message_id
        self.save(data)

    def mark_watched(self, index: int) -> None:
        data = self.load()
        session = _require_session(data)
        watched = set(int(value) for value in session.get("watched_items", []))
        watched.add(index)
        session["watched_items"] = sorted(watched)
        while session["cursor"] in watched and session["cursor"] < session["total_items"]:
            session["cursor"] += 1
        self.save(data)

    def complete_active_day(self) -> None:
        data = self.load()
        session = _require_session(data)
        day = int(session["day"])
        data["completed_days"][str(day)] = {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        data["active_session"] = None
        data["next_day"] = day + 1
        self.save(data)

    def skip_active_day(self) -> int:
        data = self.load()
        session = _require_session(data)
        day = int(session["day"])
        data["completed_days"][str(day)] = {
            "status": "skipped",
            "skipped_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        data["active_session"] = None
        data["next_day"] = day + 1
        self.save(data)
        return day

    def record_checkpoint(self, kind: str, local_date: str) -> None:
        data = self.load()
        data["checkpoints"].setdefault(local_date, {})[kind] = True
        self.save(data)

    def checkpoint_sent(self, kind: str, local_date: str) -> bool:
        return bool(self.load().get("checkpoints", {}).get(local_date, {}).get(kind))

    def set_runtime_config(
        self,
        *,
        timezone_name: str | None = None,
        start_time: str | None = None,
        nudge_time: str | None = None,
        reminder_time: str | None = None,
    ) -> dict:
        data = self.load()
        runtime = data.setdefault("runtime_config", {})
        if timezone_name is not None:
            runtime["timezone"] = timezone_name
        if start_time is not None:
            runtime["start_time"] = start_time
        if nudge_time is not None:
            runtime["nudge_time"] = nudge_time
        if reminder_time is not None:
            runtime["reminder_time"] = reminder_time
        self.save(data)
        return runtime


class DryRunTelegramClient:
    def __init__(self) -> None:
        self.actions: list[dict[str, Any]] = []

    def send_message(self, chat_id: str, text: str, reply_markup: dict[str, Any] | None = None) -> dict:
        action = {"type": "message", "chat_id": chat_id, "text": text}
        if reply_markup is not None:
            action["reply_markup"] = reply_markup
        self.actions.append(action)
        return {"message_id": len(self.actions)}

    def send_video(
        self,
        chat_id: str,
        video_path: Path,
        caption: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict:
        action = {
            "type": "video",
            "chat_id": chat_id,
            "path": str(video_path),
            "caption": caption,
        }
        if reply_markup is not None:
            action["reply_markup"] = reply_markup
        self.actions.append(action)
        return {"message_id": len(self.actions)}


class DailySender:
    def __init__(
        self,
        output_dir: Path,
        state: BotStateStore,
        telegram: TelegramSender,
        chat_id: str,
    ) -> None:
        self.output_dir = output_dir
        self.state = state
        self.telegram = telegram
        self.chat_id = chat_id

    def preview_day(self, day: int) -> list[ResolvedScheduleItem]:
        return resolve_schedule_outputs(build_day_schedule(day), self.output_dir)

    def send_day(self, day: int, force: bool = False, dry_run: bool = False) -> SendResult:
        if self.state.was_sent(day) and not force:
            return SendResult(day=day, sent=False, message_ids=[], skipped_reason="day already sent")

        items = self.preview_day(day)
        message_ids: list[int] = []
        message_ids.append(_message_id(self.telegram.send_message(self.chat_id, f"Day {day}")))
        for item in items:
            message_ids.append(
                _message_id(self.telegram.send_video(self.chat_id, item.path, item.caption))
            )

        if not dry_run:
            self.state.record_sent(day=day, message_ids=message_ids)
        return SendResult(day=day, sent=True, message_ids=message_ids)

    def send_next_day(self, force: bool = False, dry_run: bool = False) -> SendResult:
        return self.send_day(day=self.state.next_day(), force=force, dry_run=dry_run)


class InteractiveDailySender:
    def __init__(
        self,
        output_dir: Path,
        state: BotStateStore,
        telegram: TelegramSender,
        chat_id: str,
    ) -> None:
        self.output_dir = output_dir
        self.state = state
        self.telegram = telegram
        self.chat_id = chat_id

    def start_or_resume_day(self, local_date: str) -> SendResult:
        session = self.state.current_session()
        if session is None:
            day = self.state.next_day()
            items = self._items(day)
            self.state.start_day(day=day, total_items=len(items), local_date=local_date)
            self.telegram.send_message(self.chat_id, f"Day {day}")
        else:
            day = int(session["day"])
            self.telegram.send_message(self.chat_id, f"Resuming Day {day}")
        result = self.send_current_item()
        self.state.record_checkpoint("start", local_date)
        return result

    def send_current_item(self) -> SendResult:
        session = self.state.current_session()
        if session is None:
            return SendResult(day=0, sent=False, message_ids=[], skipped_reason="no active session")
        day = int(session["day"])
        index = int(session["cursor"])
        if index >= int(session["total_items"]):
            self.state.complete_active_day()
            message_id = _message_id(self.telegram.send_message(self.chat_id, f"Great job for today. Day {day} complete."))
            return SendResult(day=day, sent=True, message_ids=[message_id])
        item = self._items(day)[index]
        result = self.telegram.send_video(
            self.chat_id,
            item.path,
            item.caption,
            reply_markup=_watched_keyboard(day=day, index=index),
        )
        message_id = _message_id(result)
        self.state.mark_item_sent(index=index, message_id=message_id)
        return SendResult(day=day, sent=True, message_ids=[message_id])

    def mark_watched(self, day: int, index: int) -> SendResult:
        session = self.state.current_session()
        if session is None:
            return SendResult(day=day, sent=False, message_ids=[], skipped_reason="no active session")
        if int(session["day"]) != day:
            return SendResult(day=day, sent=False, message_ids=[], skipped_reason="callback day is not active")
        watched = set(int(value) for value in session.get("watched_items", []))
        if index in watched:
            return SendResult(day=day, sent=False, message_ids=[], skipped_reason="item already watched")
        if index != int(session["cursor"]):
            return SendResult(day=day, sent=False, message_ids=[], skipped_reason="callback item is not current")
        self.state.mark_watched(index)
        session = self.state.current_session()
        if session is None or int(session["cursor"]) >= int(session["total_items"]):
            self.state.complete_active_day()
            message_id = _message_id(self.telegram.send_message(self.chat_id, f"Great job for today. Day {day} complete."))
            return SendResult(day=day, sent=True, message_ids=[message_id])
        return self.send_current_item()

    def send_nudge(self, local_date: str) -> SendResult:
        return self._send_pending_message(
            kind="nudge",
            local_date=local_date,
            template="Hey, watch an episode while eating something. You still have {remaining} left for today.",
        )

    def send_reminder(self, local_date: str) -> SendResult:
        return self._send_pending_message(
            kind="reminder",
            local_date=local_date,
            template="Come on man, it's just 5 min an episode. You still have {remaining} left for today.",
        )

    def skip_active_day(self) -> SendResult:
        session = self.state.current_session()
        if session is None:
            return SendResult(day=0, sent=False, message_ids=[], skipped_reason="no active session")
        day = self.state.skip_active_day()
        message_id = _message_id(self.telegram.send_message(self.chat_id, f"Skipped Day {day}."))
        return SendResult(day=day, sent=True, message_ids=[message_id])

    def status_text(self) -> str:
        session = self.state.current_session()
        if session is None:
            return f"No active day. Next learner day: {self.state.next_day()}"
        remaining = int(session["total_items"]) - int(session["cursor"])
        return f"Active Day {session['day']}: {remaining} item(s) left. Next learner day: {self.state.next_day()}"

    def _send_pending_message(self, kind: str, local_date: str, template: str) -> SendResult:
        session = self.state.current_session()
        if session is None:
            return SendResult(day=0, sent=False, message_ids=[], skipped_reason="no active session")
        day = int(session["day"])
        if self.state.checkpoint_sent(kind, local_date):
            return SendResult(day=day, sent=False, message_ids=[], skipped_reason=f"{kind} already sent")
        remaining = int(session["total_items"]) - int(session["cursor"])
        if remaining <= 0:
            return SendResult(day=day, sent=False, message_ids=[], skipped_reason="day already complete")
        message_id = _message_id(
            self.telegram.send_message(
                self.chat_id,
                template.format(remaining=remaining),
                reply_markup=_current_item_keyboard(day=day, index=int(session["cursor"])),
            )
        )
        self.state.record_checkpoint(kind, local_date)
        return SendResult(day=day, sent=True, message_ids=[message_id])

    def _items(self, day: int) -> list[ResolvedScheduleItem]:
        return resolve_schedule_outputs(build_day_schedule(day), self.output_dir)


def _message_id(result: dict) -> int:
    value = result.get("message_id")
    if value is None:
        return 0
    return int(value)


def _watched_keyboard(day: int, index: int) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "✅ Watched", "callback_data": f"watched:{day}:{index}"}]]}


def _current_item_keyboard(day: int, index: int) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "✅ Watched", "callback_data": f"watched:{day}:{index}"}],
            [{"text": "🔁 Resend current", "callback_data": f"resend:{day}:{index}"}],
        ]
    }


def _default_state() -> dict:
    return {
        "sent_days": {},
        "completed_days": {},
        "active_session": None,
        "checkpoints": {},
        "runtime_config": {},
        "next_day": 1,
    }


def _normalize_state(data: dict) -> dict:
    normalized = _default_state()
    normalized.update(data)
    normalized["sent_days"] = normalized.get("sent_days") or {}
    normalized["completed_days"] = normalized.get("completed_days") or {}
    normalized["checkpoints"] = normalized.get("checkpoints") or {}
    normalized["runtime_config"] = normalized.get("runtime_config") or {}
    return normalized


def _require_session(data: dict) -> dict:
    session = data.get("active_session")
    if session is None:
        raise RuntimeError("no active session")
    return session
