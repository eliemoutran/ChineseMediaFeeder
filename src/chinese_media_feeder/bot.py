from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from chinese_media_feeder.schedule import ResolvedScheduleItem, build_day_schedule, resolve_schedule_outputs


class TelegramSender(Protocol):
    def send_message(self, chat_id: str, text: str) -> dict: ...

    def send_video(self, chat_id: str, video_path: Path, caption: str) -> dict: ...


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
            return {"sent_days": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def was_sent(self, day: int) -> bool:
        return str(day) in self.load()["sent_days"]

    def next_day(self) -> int:
        sent_days = [int(day) for day in self.load()["sent_days"]]
        return max(sent_days, default=0) + 1

    def record_sent(self, day: int, message_ids: list[int]) -> None:
        data = self.load()
        data["sent_days"][str(day)] = {
            "message_ids": message_ids,
            "sent_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        self.save(data)


class DryRunTelegramClient:
    def __init__(self) -> None:
        self.actions: list[dict[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> dict:
        self.actions.append({"type": "message", "chat_id": chat_id, "text": text})
        return {"message_id": len(self.actions)}

    def send_video(self, chat_id: str, video_path: Path, caption: str) -> dict:
        self.actions.append(
            {
                "type": "video",
                "chat_id": chat_id,
                "path": str(video_path),
                "caption": caption,
            }
        )
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


def _message_id(result: dict) -> int:
    value = result.get("message_id")
    if value is None:
        return 0
    return int(value)
