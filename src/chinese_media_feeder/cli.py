from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Annotated

import typer

from chinese_media_feeder.bot import BotStateStore, DailySender, DryRunTelegramClient, InteractiveDailySender
from chinese_media_feeder.bot_scheduler import BotScheduleConfig, due_checkpoints, parse_hhmm
from chinese_media_feeder.config import Settings
from chinese_media_feeder.episodes import EpisodePaths, scan_input_videos
from chinese_media_feeder.manifest import ManifestStore
from chinese_media_feeder.openai_client import OpenAIAdapter
from chinese_media_feeder.pipeline import EpisodeProcessor, ProgressEvent
from chinese_media_feeder.schedule import MissingScheduleOutputError, build_day_schedule, resolve_schedule_outputs
from chinese_media_feeder.telegram import TelegramClient


app = typer.Typer(help="Generate Mandarin learner video variants.")
schedule_app = typer.Typer(help="Preview the learner rotation schedule.")
bot_app = typer.Typer(help="Send generated videos through Telegram.")
app.add_typer(schedule_app, name="schedule")
app.add_typer(bot_app, name="bot")


def configure_unicode_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


@app.callback()
def configure_cli() -> None:
    configure_unicode_output()


@app.command()
def scan() -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    videos = scan_input_videos(settings.input_dir)
    for video in videos:
        paths = EpisodePaths.from_input(video, settings.work_dir, settings.output_dir)
        typer.echo(f"{paths.slug}\t{video}")
    if not videos:
        typer.echo(f"No supported videos found in {settings.input_dir}")


def echo_progress(event: ProgressEvent) -> None:
    typer.echo(f"{event.slug}\t{event.step}={event.status}")


@app.command("process")
def process_file(
    input_file: Annotated[Path, typer.Argument(exists=True, readable=True, dir_okay=False)],
    force: Annotated[bool, typer.Option("--force", help="Regenerate existing artifacts.")] = False,
) -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    if settings.openai_api_key is None:
        raise typer.BadParameter("OPENAI_API_KEY is required for processing.")
    adapter = OpenAIAdapter(
        api_key=settings.openai_api_key,
        transcribe_model=settings.transcribe_model,
        translation_model=settings.translation_model,
    )
    processor = EpisodeProcessor(settings=settings, openai=adapter, progress_callback=echo_progress)
    paths = processor.process(input_file, force=force)
    typer.echo(f"Generated {paths.output_dir}")


@app.command("process-all")
def process_all(
    force: Annotated[bool, typer.Option("--force", help="Regenerate existing artifacts.")] = False,
) -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    videos = scan_input_videos(settings.input_dir)
    if not videos:
        typer.echo(f"No supported videos found in {settings.input_dir}")
        return
    if settings.openai_api_key is None:
        raise typer.BadParameter("OPENAI_API_KEY is required for processing.")
    adapter = OpenAIAdapter(
        api_key=settings.openai_api_key,
        transcribe_model=settings.transcribe_model,
        translation_model=settings.translation_model,
    )
    processor = EpisodeProcessor(settings=settings, openai=adapter, progress_callback=echo_progress)
    failed = False
    for video in videos:
        try:
            paths = processor.process(video, force=force)
        except Exception as exc:
            failed = True
            typer.echo(f"Failed {video}: {exc}")
            continue
        typer.echo(f"Generated {paths.output_dir}")
    if failed:
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    settings = Settings.from_env()
    data = ManifestStore(settings.manifest_path).load()
    episodes = data["episodes"]
    if not episodes:
        typer.echo("No episodes processed.")
        return
    for slug, episode in sorted(episodes.items()):
        steps = episode.get("steps", {})
        statuses = []
        for name, info in steps.items():
            status = info.get("status")
            step_status = f"{name}={status}"
            error = info.get("error")
            if error:
                step_status = f"{step_status}({error})"
            statuses.append(step_status)
        typer.echo(f"{slug}\t{', '.join(statuses)}")


@schedule_app.command("preview")
def preview_schedule(
    day: Annotated[int, typer.Option("--day", min=1, help="Learner day to preview.")],
) -> None:
    settings = Settings.from_env()
    items = resolve_schedule_outputs(build_day_schedule(day), settings.output_dir)
    typer.echo(f"Day {day}")
    for item in items:
        typer.echo(f"{item.caption}\t{item.path}")


@bot_app.command("send-day")
def send_bot_day(
    day: Annotated[int, typer.Option("--day", min=1, help="Learner day to send.")],
    force: Annotated[bool, typer.Option("--force", help="Resend even when state says this day was sent.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Resolve and simulate sends without Telegram calls.")] = False,
) -> None:
    settings = Settings.from_env()
    sender = _build_daily_sender(settings, dry_run=dry_run)
    result = sender.send_day(day=day, force=force, dry_run=dry_run)
    if result.sent:
        suffix = " (dry-run)" if dry_run else ""
        typer.echo(f"Sent day {day}{suffix}: {len(result.message_ids)} messages")
        return
    typer.echo(f"Skipped day {day}: {result.skipped_reason}")


@bot_app.command("run")
def run_bot(
    once: Annotated[bool, typer.Option("--once", help="Send one next unsent day and exit.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Resolve and simulate sends without Telegram calls.")] = False,
) -> None:
    settings = Settings.from_env()
    sender = _build_interactive_sender(settings, dry_run=dry_run)
    client = sender.telegram if not dry_run else None
    update_offset: int | None = None
    while True:
        _process_due_checkpoints(settings, sender, dry_run=dry_run)
        if client is not None and hasattr(client, "get_updates"):
            updates = client.get_updates(offset=update_offset, timeout=20)
            for update in updates:
                update_offset = max(update_offset or 0, int(update["update_id"]) + 1)
                _process_update(sender, update, settings.telegram_chat_id or "")
        if once:
            return
        time.sleep(min(settings.bot_interval_seconds, 30))


@bot_app.command("state")
def bot_state() -> None:
    settings = Settings.from_env()
    state = BotStateStore(settings.bot_state_path)
    data = state.load()
    session = data.get("active_session")
    if session is None:
        typer.echo(f"No active day. Next learner day: {state.next_day()}")
    else:
        remaining = int(session["total_items"]) - int(session["cursor"])
        typer.echo(f"Active Day {session['day']}: {remaining} item(s) left. Next learner day: {state.next_day()}")
    runtime = _effective_schedule_config(settings, state)
    typer.echo(
        f"Schedule: {runtime.start_time} start, {runtime.nudge_time} nudge, "
        f"{runtime.reminder_time} reminder ({runtime.timezone_name})"
    )


@bot_app.command("reset")
def bot_reset() -> None:
    settings = Settings.from_env()
    state = BotStateStore(settings.bot_state_path)
    state.reset()
    typer.echo("Bot state reset. Next learner day: 1")


@bot_app.command("set-day")
def bot_set_day(day: Annotated[int, typer.Option("--day", min=1, help="Next learner day.")]) -> None:
    settings = Settings.from_env()
    state = BotStateStore(settings.bot_state_path)
    state.set_next_day(day)
    typer.echo(f"Next learner day set to {day}")


@bot_app.command("set-start")
def bot_set_start(
    send_time: Annotated[str, typer.Option("--time", help="Daily start time in HH:MM.")],
    timezone_name: Annotated[str, typer.Option("--timezone", help="IANA timezone name.")] = "Asia/Manila",
) -> None:
    parse_hhmm(send_time)
    settings = Settings.from_env()
    state = BotStateStore(settings.bot_state_path)
    state.set_runtime_config(timezone_name=timezone_name, start_time=send_time)
    typer.echo(f"Start time set to {send_time} ({timezone_name})")


@bot_app.command("set-nudge")
def bot_set_nudge(send_time: Annotated[str, typer.Option("--time", help="Nudge time in HH:MM.")]) -> None:
    parse_hhmm(send_time)
    settings = Settings.from_env()
    state = BotStateStore(settings.bot_state_path)
    state.set_runtime_config(nudge_time=send_time)
    typer.echo(f"Nudge time set to {send_time}")


@bot_app.command("set-reminder")
def bot_set_reminder(send_time: Annotated[str, typer.Option("--time", help="Reminder time in HH:MM.")]) -> None:
    parse_hhmm(send_time)
    settings = Settings.from_env()
    state = BotStateStore(settings.bot_state_path)
    state.set_runtime_config(reminder_time=send_time)
    typer.echo(f"Reminder time set to {send_time}")


@bot_app.command("test")
def test_bot(
    with_video: Annotated[bool, typer.Option("--with-video", help="Also send the first mode 1 video.")] = False,
) -> None:
    settings = Settings.from_env()
    client = _build_telegram_client(settings)
    try:
        client.send_message(settings.telegram_chat_id or "", "ChineseMediaFeeder bot test")
        sent_video = False
        if with_video:
            video = _first_mode1_video(settings.output_dir)
            client.send_video(settings.telegram_chat_id or "", video, "ChineseMediaFeeder test video")
            sent_video = True
    finally:
        client.close()
    if sent_video:
        typer.echo("Sent Telegram test message and video")
    else:
        typer.echo("Sent Telegram test message")


def _build_daily_sender(settings: Settings, dry_run: bool = False) -> DailySender:
    if not dry_run and not settings.telegram_bot_token:
        raise typer.BadParameter("TELEGRAM_BOT_TOKEN is required for bot sending.")
    if not settings.telegram_chat_id:
        raise typer.BadParameter("TELEGRAM_CHAT_ID is required for bot sending.")
    telegram = DryRunTelegramClient() if dry_run else _build_telegram_client(settings)
    return DailySender(
        output_dir=settings.output_dir,
        state=BotStateStore(settings.bot_state_path),
        telegram=telegram,
        chat_id=settings.telegram_chat_id,
    )


def _build_interactive_sender(settings: Settings, dry_run: bool = False) -> InteractiveDailySender:
    if not dry_run and not settings.telegram_bot_token:
        raise typer.BadParameter("TELEGRAM_BOT_TOKEN is required for bot sending.")
    if not settings.telegram_chat_id:
        raise typer.BadParameter("TELEGRAM_CHAT_ID is required for bot sending.")
    telegram = DryRunTelegramClient() if dry_run else _build_telegram_client(settings)
    return InteractiveDailySender(
        output_dir=settings.output_dir,
        state=BotStateStore(settings.bot_state_path),
        telegram=telegram,
        chat_id=settings.telegram_chat_id,
    )


def _effective_schedule_config(settings: Settings, state: BotStateStore) -> BotScheduleConfig:
    runtime = state.load().get("runtime_config", {})
    return BotScheduleConfig(
        timezone_name=runtime.get("timezone") or settings.bot_timezone,
        start_time=runtime.get("start_time") or settings.bot_start_time,
        nudge_time=runtime.get("nudge_time") or settings.bot_nudge_time,
        reminder_time=runtime.get("reminder_time") or settings.bot_reminder_time,
    )


def _process_due_checkpoints(settings: Settings, sender: InteractiveDailySender, dry_run: bool = False) -> None:
    original_state_exists = sender.state.path.exists()
    original_state = sender.state.load()
    config = _effective_schedule_config(settings, sender.state)
    due = due_checkpoints(
        now=datetime.now(timezone.utc),
        config=config,
        already_sent=sender.state.checkpoint_sent,
    )
    had_active_session = sender.state.current_session() is not None
    late_first_start = any(checkpoint.kind == "start" for checkpoint in due) and not had_active_session
    for checkpoint in due:
        if late_first_start and checkpoint.kind != "start":
            sender.state.record_checkpoint(checkpoint.kind, checkpoint.local_date)
            typer.echo(f"Skipped {checkpoint.kind}: late first start")
            continue
        if checkpoint.kind == "start":
            result = sender.start_or_resume_day(local_date=checkpoint.local_date)
        elif checkpoint.kind == "nudge":
            result = sender.send_nudge(local_date=checkpoint.local_date)
        else:
            result = sender.send_reminder(local_date=checkpoint.local_date)
        if not result.sent and result.skipped_reason in {"no active session", "day already complete"}:
            sender.state.record_checkpoint(checkpoint.kind, checkpoint.local_date)
        if result.sent:
            typer.echo(f"Sent {checkpoint.kind} for day {result.day}: {len(result.message_ids)} messages")
        else:
            typer.echo(f"Skipped {checkpoint.kind}: {result.skipped_reason}")
    if dry_run:
        if original_state_exists:
            sender.state.save(original_state)
        elif sender.state.path.exists():
            sender.state.path.unlink()


def _process_update(sender: InteractiveDailySender, update: dict, expected_chat_id: str) -> None:
    callback = update.get("callback_query")
    if callback is not None:
        _process_callback(sender, callback, expected_chat_id)
        return
    message = update.get("message")
    if message is None:
        return
    chat_id = str(message.get("chat", {}).get("id", ""))
    if chat_id != expected_chat_id:
        return
    text = str(message.get("text") or "").strip()
    if text == "/state":
        sender.telegram.send_message(expected_chat_id, sender.status_text())
    elif text == "/today":
        sender.send_current_item()
    elif text == "/skip":
        sender.skip_active_day()
    elif text == "/reset":
        sender.state.reset()
        sender.telegram.send_message(expected_chat_id, "Bot state reset. Next learner day: 1")
    elif text.startswith("/setstart "):
        value = text.removeprefix("/setstart ").strip()
        parse_hhmm(value)
        sender.state.set_runtime_config(start_time=value)
        sender.telegram.send_message(expected_chat_id, f"Start time set to {value}")
    elif text.startswith("/setnudge "):
        value = text.removeprefix("/setnudge ").strip()
        parse_hhmm(value)
        sender.state.set_runtime_config(nudge_time=value)
        sender.telegram.send_message(expected_chat_id, f"Nudge time set to {value}")
    elif text.startswith("/setreminder "):
        value = text.removeprefix("/setreminder ").strip()
        parse_hhmm(value)
        sender.state.set_runtime_config(reminder_time=value)
        sender.telegram.send_message(expected_chat_id, f"Reminder time set to {value}")
    elif text == "/help":
        sender.telegram.send_message(
            expected_chat_id,
            "/state\n/today\n/setstart 07:00\n/setnudge 14:00\n/setreminder 22:00\n/skip\n/reset",
        )


def _process_callback(sender: InteractiveDailySender, callback: dict, expected_chat_id: str) -> None:
    chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
    callback_id = str(callback.get("id") or "")
    if chat_id != expected_chat_id:
        if hasattr(sender.telegram, "answer_callback_query"):
            sender.telegram.answer_callback_query(callback_id, "Ignored")
        return
    data = str(callback.get("data") or "")
    parts = data.split(":")
    if len(parts) != 3:
        return
    action, day_text, index_text = parts
    day = int(day_text)
    index = int(index_text)
    if action == "watched":
        result = sender.mark_watched(day=day, index=index)
        if hasattr(sender.telegram, "answer_callback_query"):
            sender.telegram.answer_callback_query(callback_id, "Recorded" if result.sent else "Already handled")
    elif action == "resend":
        sender.send_current_item()
        if hasattr(sender.telegram, "answer_callback_query"):
            sender.telegram.answer_callback_query(callback_id, "Resent")


def _build_telegram_client(settings: Settings) -> TelegramClient:
    if not settings.telegram_bot_token:
        raise typer.BadParameter("TELEGRAM_BOT_TOKEN is required for bot sending.")
    if not settings.telegram_chat_id:
        raise typer.BadParameter("TELEGRAM_CHAT_ID is required for bot sending.")
    return TelegramClient(settings.telegram_bot_token)


def _first_mode1_video(output_dir: Path) -> Path:
    videos = sorted(output_dir.glob("*/*.mode1-nosubs.mp4"))
    if not videos:
        raise typer.BadParameter(f"No mode 1 videos found in {output_dir}.")
    return videos[0]


def main() -> None:
    configure_unicode_output()
    app()


if __name__ == "__main__":
    main()
