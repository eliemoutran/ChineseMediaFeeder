from datetime import datetime, timezone

from chinese_media_feeder.bot_scheduler import BotScheduleConfig, due_checkpoints, local_date_string, parse_hhmm


def test_parse_hhmm_accepts_24_hour_times():
    assert parse_hhmm("07:00").hour == 7
    assert parse_hhmm("22:15").minute == 15


def test_parse_hhmm_rejects_invalid_times():
    try:
        parse_hhmm("25:00")
    except ValueError as exc:
        assert "HH:MM" in str(exc)
    else:
        raise AssertionError("expected invalid time to fail")


def test_local_date_string_uses_configured_timezone():
    now = datetime(2026, 5, 21, 23, 30, tzinfo=timezone.utc)

    assert local_date_string(now, "Asia/Manila") == "2026-05-22"


def test_due_checkpoints_returns_start_after_start_time_once():
    config = BotScheduleConfig(
        timezone_name="Asia/Manila",
        start_time="07:00",
        nudge_time="14:00",
        reminder_time="22:00",
    )
    now = datetime(2026, 5, 21, 23, 30, tzinfo=timezone.utc)

    due = due_checkpoints(now=now, config=config, already_sent=lambda kind, date: False)

    assert [checkpoint.kind for checkpoint in due] == ["start"]
    assert due[0].local_date == "2026-05-22"


def test_due_checkpoints_includes_nudge_and_reminder_after_their_times():
    config = BotScheduleConfig(
        timezone_name="Asia/Manila",
        start_time="07:00",
        nudge_time="14:00",
        reminder_time="22:00",
    )
    now = datetime(2026, 5, 22, 14, 30, tzinfo=timezone.utc)

    due = due_checkpoints(now=now, config=config, already_sent=lambda kind, date: kind == "start")

    assert [checkpoint.kind for checkpoint in due] == ["nudge", "reminder"]


def test_due_checkpoints_skips_checkpoint_already_sent_for_local_date():
    config = BotScheduleConfig(
        timezone_name="Asia/Manila",
        start_time="07:00",
        nudge_time="14:00",
        reminder_time="22:00",
    )
    now = datetime(2026, 5, 22, 6, 30, tzinfo=timezone.utc)

    due = due_checkpoints(
        now=now,
        config=config,
        already_sent=lambda kind, date: kind in {"start", "nudge"},
    )

    assert [checkpoint.kind for checkpoint in due] == []
