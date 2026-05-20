from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".m4v", ".webm"}


def slugify_episode(path: Path) -> str:
    ascii_stem = path.stem.encode("ascii", errors="ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_stem).strip("-").lower()
    return slug or "episode"


@dataclass(frozen=True)
class EpisodePaths:
    slug: str
    input_path: Path
    work_dir: Path
    output_dir: Path
    audio_path: Path
    raw_transcript_path: Path
    normalized_cues_path: Path
    pinyin_subtitle_path: Path
    alternating_subtitle_path: Path
    mode1_path: Path
    mode2_path: Path
    mode3_path: Path

    @classmethod
    def from_input(cls, input_path: Path, work_root: Path, output_root: Path) -> "EpisodePaths":
        slug = slugify_episode(input_path)
        work_dir = work_root / slug
        output_dir = output_root / slug
        return cls(
            slug=slug,
            input_path=input_path,
            work_dir=work_dir,
            output_dir=output_dir,
            audio_path=work_dir / "audio.m4a",
            raw_transcript_path=work_dir / "transcript.raw.json",
            normalized_cues_path=work_dir / "cues.normalized.json",
            pinyin_subtitle_path=work_dir / "subtitles.pinyin.ass",
            alternating_subtitle_path=work_dir / "subtitles.alternating.ass",
            mode1_path=output_dir / f"{slug}.mode1-nosubs.mp4",
            mode2_path=output_dir / f"{slug}.mode2-pinyin.mp4",
            mode3_path=output_dir / f"{slug}.mode3-alternating.mp4",
        )

    def ensure_directories(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


def scan_input_videos(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    return sorted(
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
    )
