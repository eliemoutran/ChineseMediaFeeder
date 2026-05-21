from pathlib import Path

import pytest

from chinese_media_feeder.bot import BotStateStore, DailySender, DryRunTelegramClient
from chinese_media_feeder.schedule import MissingScheduleOutputError, build_day_schedule


class RecordingTelegramClient:
    def __init__(self):
        self.messages = []
        self.videos = []

    def send_message(self, chat_id: str, text: str):
        self.messages.append((chat_id, text))
        return {"message_id": len(self.messages)}

    def send_video(self, chat_id: str, video_path: Path, caption: str):
        self.videos.append((chat_id, video_path, caption))
        return {"message_id": len(self.messages) + len(self.videos)}


def make_output(output_dir: Path, slug: str, suffix: str):
    episode_dir = output_dir / slug
    episode_dir.mkdir(parents=True, exist_ok=True)
    path = episode_dir / f"{slug}{suffix}"
    path.write_bytes(b"video")
    return path


def test_bot_state_store_starts_empty_and_records_sent_day(tmp_path):
    store = BotStateStore(tmp_path / "state.json")

    assert store.was_sent(1) is False

    store.record_sent(day=1, message_ids=[10, 11])

    assert store.was_sent(1) is True
    assert store.load()["sent_days"]["1"]["message_ids"] == [10, 11]


def test_daily_sender_sends_day_and_records_state(tmp_path):
    output_dir = tmp_path / "output"
    video = make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    telegram = RecordingTelegramClient()
    sender = DailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")

    result = sender.send_day(day=1)

    assert result.sent is True
    assert telegram.messages == [("123", "Day 1")]
    assert telegram.videos == [("123", video, "📺 ep1.mp4 - Mode 1")]
    assert state.was_sent(1) is True


def test_daily_sender_skips_previously_sent_day_without_force(tmp_path):
    output_dir = tmp_path / "output"
    make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    state.record_sent(day=1, message_ids=[1])
    telegram = RecordingTelegramClient()
    sender = DailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")

    result = sender.send_day(day=1)

    assert result.sent is False
    assert result.skipped_reason == "day already sent"
    assert telegram.messages == []
    assert telegram.videos == []


def test_daily_sender_force_resends_previously_sent_day(tmp_path):
    output_dir = tmp_path / "output"
    make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    state.record_sent(day=1, message_ids=[1])
    telegram = RecordingTelegramClient()
    sender = DailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")

    result = sender.send_day(day=1, force=True)

    assert result.sent is True
    assert len(telegram.videos) == 1


def test_daily_sender_dry_run_does_not_record_state(tmp_path):
    output_dir = tmp_path / "output"
    make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    telegram = DryRunTelegramClient()
    sender = DailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")

    result = sender.send_day(day=1, dry_run=True)

    assert result.sent is True
    assert state.was_sent(1) is False
    assert telegram.actions == [
        {"type": "message", "chat_id": "123", "text": "Day 1"},
        {
            "type": "video",
            "chat_id": "123",
            "path": str(output_dir / "peppa-001" / "peppa-001.mode1-nosubs.mp4"),
            "caption": "📺 ep1.mp4 - Mode 1",
        },
    ]


def test_daily_sender_raises_when_scheduled_output_missing(tmp_path):
    sender = DailySender(
        output_dir=tmp_path / "output",
        state=BotStateStore(tmp_path / "state.json"),
        telegram=RecordingTelegramClient(),
        chat_id="123",
    )

    with pytest.raises(MissingScheduleOutputError):
        sender.send_day(day=1)


def test_daily_sender_previews_schedule_without_sending(tmp_path):
    output_dir = tmp_path / "output"
    make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    sender = DailySender(
        output_dir=output_dir,
        state=BotStateStore(tmp_path / "state.json"),
        telegram=RecordingTelegramClient(),
        chat_id="123",
    )

    items = sender.preview_day(day=1)

    assert [(item.day, item.episode_number, item.mode) for item in items] == [
        (build_day_schedule(1)[0].day, 1, 1)
    ]
