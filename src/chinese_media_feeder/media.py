from __future__ import annotations

import subprocess
from pathlib import Path


def build_extract_audio_command(input_path: Path, output_path: Path, bitrate: str = "48k") -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        bitrate,
        str(output_path),
    ]


def build_mode1_command(input_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def build_burn_subtitles_command(input_path: Path, subtitle_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        f"ass={subtitle_path}",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


class MediaRunner:
    def run(self, command: list[str]) -> None:
        subprocess.run(command, check=True)

    def extract_audio(self, input_path: Path, output_path: Path, bitrate: str = "48k") -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.run(build_extract_audio_command(input_path, output_path, bitrate=bitrate))

    def render_mode1(self, input_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.run(build_mode1_command(input_path, output_path))

    def burn_subtitles(self, input_path: Path, subtitle_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.run(build_burn_subtitles_command(input_path, subtitle_path, output_path))
