from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated

import typer

from chinese_media_feeder.config import Settings
from chinese_media_feeder.episodes import EpisodePaths, scan_input_videos
from chinese_media_feeder.manifest import ManifestStore
from chinese_media_feeder.openai_client import OpenAIAdapter
from chinese_media_feeder.pipeline import EpisodeProcessor


app = typer.Typer(help="Generate Mandarin learner video variants.")


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
    processor = EpisodeProcessor(settings=settings, openai=adapter)
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
    processor = EpisodeProcessor(settings=settings, openai=adapter)
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


def main() -> None:
    configure_unicode_output()
    app()


if __name__ == "__main__":
    main()
