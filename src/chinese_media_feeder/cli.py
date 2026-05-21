from __future__ import annotations

from pathlib import Path
import sys
import time
from typing import Annotated

import typer

from chinese_media_feeder.bot import BotStateStore, DailySender, DryRunTelegramClient
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
    sender = _build_daily_sender(settings, dry_run=dry_run)
    while True:
        day = sender.state.next_day()
        result = sender.send_day(day=day, dry_run=dry_run)
        if result.sent:
            suffix = " (dry-run)" if dry_run else ""
            typer.echo(f"Sent day {day}{suffix}: {len(result.message_ids)} messages")
        else:
            typer.echo(f"Skipped day {day}: {result.skipped_reason}")
        if once:
            return
        time.sleep(settings.bot_interval_seconds)


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
