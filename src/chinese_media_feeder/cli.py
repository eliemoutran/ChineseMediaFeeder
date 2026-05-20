from __future__ import annotations

from pathlib import Path

import typer

from chinese_media_feeder.config import Settings
from chinese_media_feeder.episodes import EpisodePaths, scan_input_videos
from chinese_media_feeder.manifest import ManifestStore
from chinese_media_feeder.openai_client import OpenAIAdapter
from chinese_media_feeder.pipeline import EpisodeProcessor


app = typer.Typer(help="Generate Mandarin learner video variants.")


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


@app.command("process")
def process_file(input_file: Path, force: bool = False) -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    if settings.openai_api_key is None:
        raise typer.BadParameter("OPENAI_API_KEY is required for processing.")
    adapter = OpenAIAdapter(
        api_key=settings.openai_api_key,
        transcribe_model=settings.transcribe_model,
        translation_model=settings.translation_model,
    )
    processor = EpisodeProcessor(settings=settings, openai=adapter)
    paths = processor.process(input_file, force=force)
    typer.echo(f"Generated {paths.output_dir}")


@app.command("process-all")
def process_all(force: bool = False) -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    if settings.openai_api_key is None:
        raise typer.BadParameter("OPENAI_API_KEY is required for processing.")
    adapter = OpenAIAdapter(
        api_key=settings.openai_api_key,
        transcribe_model=settings.transcribe_model,
        translation_model=settings.translation_model,
    )
    processor = EpisodeProcessor(settings=settings, openai=adapter)
    for video in scan_input_videos(settings.input_dir):
        paths = processor.process(video, force=force)
        typer.echo(f"Generated {paths.output_dir}")


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
        completed = [name for name, info in steps.items() if info.get("status") == "complete"]
        typer.echo(f"{slug}\t{', '.join(completed)}")
