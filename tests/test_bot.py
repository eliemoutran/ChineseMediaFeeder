from pathlib import Path

import pytest

from chinese_media_feeder.bot import BotStateStore, DailySender, DryRunTelegramClient, InteractiveDailySender
from chinese_media_feeder.schedule import MissingScheduleOutputError, build_day_schedule


class RecordingTelegramClient:
    def __init__(self):
        self.messages = []
        self.videos = []

    def send_message(self, chat_id: str, text: str, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))
        return {"message_id": len(self.messages)}

    def send_video(self, chat_id: str, video_path: Path, caption: str, reply_markup=None):
        self.videos.append((chat_id, video_path, caption, reply_markup))
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
    assert telegram.messages == [("123", "Day 1", None)]
    assert telegram.videos == [("123", video, "📺 ep1.mp4 - Mode 1", None)]
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


def test_bot_state_store_tracks_interactive_active_session(tmp_path):
    state = BotStateStore(tmp_path / "state.json")

    state.start_day(day=3, total_items=3, local_date="2026-05-22")
    state.mark_item_sent(index=0, message_id=10)
    state.mark_watched(index=0)
    state.record_checkpoint(kind="nudge", local_date="2026-05-22")

    data = state.load()
    assert data["active_session"]["day"] == 3
    assert data["active_session"]["cursor"] == 1
    assert data["active_session"]["watched_items"] == [0]
    assert data["active_session"]["sent_items"]["0"] == 10
    assert state.checkpoint_sent(kind="nudge", local_date="2026-05-22") is True
    assert state.next_day() == 3


def test_bot_state_store_completes_skips_and_resets_interactive_state(tmp_path):
    state = BotStateStore(tmp_path / "state.json")
    state.start_day(day=2, total_items=1, local_date="2026-05-22")

    state.complete_active_day()

    assert state.current_session() is None
    assert state.next_day() == 3
    assert state.load()["completed_days"]["2"]["status"] == "completed"

    state.start_day(day=3, total_items=1, local_date="2026-05-23")
    state.skip_active_day()

    assert state.current_session() is None
    assert state.next_day() == 4
    assert state.load()["completed_days"]["3"]["status"] == "skipped"

    state.reset()

    assert state.load()["completed_days"] == {}
    assert state.current_session() is None
    assert state.next_day() == 1


def test_interactive_sender_starts_day_with_first_item_only(tmp_path):
    output_dir = tmp_path / "output"
    first = make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    telegram = RecordingTelegramClient()
    sender = InteractiveDailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")

    result = sender.start_or_resume_day(local_date="2026-05-22")

    assert result.sent is True
    assert result.day == 1
    assert telegram.messages == [("123", "Day 1", None)]
    assert telegram.videos == [
        (
            "123",
            first,
            "📺 ep1.mp4 - Mode 1",
            {"inline_keyboard": [[{"text": "✅ Watched", "callback_data": "watched:1:0"}]]},
        )
    ]
    assert state.current_session()["cursor"] == 0


def test_interactive_sender_unlocks_next_item_when_watched(tmp_path):
    output_dir = tmp_path / "output"
    second = make_output(output_dir, "peppa-001", ".mode2-pinyin.mp4")
    make_output(output_dir, "peppa-002", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    telegram = RecordingTelegramClient()
    sender = InteractiveDailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")
    state.start_day(day=2, total_items=2, local_date="2026-05-22")
    sender.send_current_item()

    result = sender.mark_watched(day=2, index=0)

    assert result.sent is True
    assert telegram.videos[-1] == (
        "123",
        second,
        "🔁 ep1.mp4 - Mode 2",
        {"inline_keyboard": [[{"text": "✅ Watched", "callback_data": "watched:2:1"}]]},
    )
    assert state.current_session()["cursor"] == 1
    assert state.current_session()["watched_items"] == [0]


def test_interactive_sender_completes_day_after_final_watched_item(tmp_path):
    output_dir = tmp_path / "output"
    make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    telegram = RecordingTelegramClient()
    sender = InteractiveDailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")
    sender.start_or_resume_day(local_date="2026-05-22")

    result = sender.mark_watched(day=1, index=0)

    assert result.sent is True
    assert telegram.messages[-1] == ("123", "Great job for today. Day 1 complete.", None)
    assert state.current_session() is None
    assert state.next_day() == 2


def test_interactive_sender_duplicate_watched_callback_is_idempotent(tmp_path):
    output_dir = tmp_path / "output"
    make_output(output_dir, "peppa-001", ".mode2-pinyin.mp4")
    make_output(output_dir, "peppa-002", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    telegram = RecordingTelegramClient()
    sender = InteractiveDailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")
    state.start_day(day=2, total_items=2, local_date="2026-05-22")
    sender.send_current_item()
    sender.mark_watched(day=2, index=0)
    video_count = len(telegram.videos)

    result = sender.mark_watched(day=2, index=0)

    assert result.sent is False
    assert result.skipped_reason == "item already watched"
    assert len(telegram.videos) == video_count


def test_interactive_sender_resumes_unfinished_day_instead_of_advancing(tmp_path):
    output_dir = tmp_path / "output"
    make_output(output_dir, "peppa-001", ".mode2-pinyin.mp4")
    make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    make_output(output_dir, "peppa-002", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    telegram = RecordingTelegramClient()
    sender = InteractiveDailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")
    sender.start_or_resume_day(local_date="2026-05-22")

    result = sender.start_or_resume_day(local_date="2026-05-23")

    assert result.day == 1
    assert result.sent is True
    assert len(telegram.videos) == 2
    assert telegram.messages[-1] == ("123", "Resuming Day 1", None)


def test_interactive_sender_sends_nudge_and_reminder_once_per_date(tmp_path):
    output_dir = tmp_path / "output"
    make_output(output_dir, "peppa-001", ".mode1-nosubs.mp4")
    make_output(output_dir, "peppa-001", ".mode2-pinyin.mp4")
    make_output(output_dir, "peppa-002", ".mode1-nosubs.mp4")
    state = BotStateStore(tmp_path / "state.json")
    telegram = RecordingTelegramClient()
    sender = InteractiveDailySender(output_dir=output_dir, state=state, telegram=telegram, chat_id="123")
    state.start_day(day=2, total_items=2, local_date="2026-05-22")
    sender.send_current_item()

    nudge = sender.send_nudge(local_date="2026-05-22")
    duplicate = sender.send_nudge(local_date="2026-05-22")
    reminder = sender.send_reminder(local_date="2026-05-22")

    assert nudge.sent is True
    assert duplicate.sent is False
    assert duplicate.skipped_reason == "nudge already sent"
    assert reminder.sent is True
    assert telegram.messages[-2][1] == "Hey, watch an episode while eating something. You still have 2 left for today."
    assert telegram.messages[-1][1] == "Come on man, it's just 5 min an episode. You still have 2 left for today."
