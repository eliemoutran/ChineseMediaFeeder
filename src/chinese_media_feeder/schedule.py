from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


MODE_OUTPUT_SUFFIXES = {
    1: ".mode1-nosubs.mp4",
    2: ".mode2-pinyin.mp4",
    3: ".mode3-alternating.mp4",
}


class MissingScheduleOutputError(RuntimeError):
    def __init__(self, missing: list[str]) -> None:
        super().__init__("Missing scheduled outputs: " + ", ".join(missing))
        self.missing = missing


@dataclass(frozen=True)
class ScheduleItem:
    day: int
    episode_number: int
    mode: int
    emoji: str

    @property
    def label(self) -> str:
        return f"ep{self.episode_number}.mp4 - Mode {self.mode}"


@dataclass(frozen=True)
class ResolvedScheduleItem:
    day: int
    episode_number: int
    mode: int
    source_mode: int
    emoji: str
    slug: str
    path: Path

    @property
    def caption(self) -> str:
        return f"{self.emoji} ep{self.episode_number}.mp4 - Mode {self.mode}"


def build_day_schedule(day: int) -> list[ScheduleItem]:
    if day < 1:
        raise ValueError("day must be at least 1")

    candidates = [
        (day, 1, "📺"),
        (day - 1, 2, "🔁"),
        (day - 2, 3, "🔁"),
        (day - 5, 4, "🎯"),
    ]
    return [
        ScheduleItem(day=day, episode_number=episode_number, mode=mode, emoji=emoji)
        for episode_number, mode, emoji in candidates
        if episode_number >= 1
    ]


def resolve_schedule_outputs(items: list[ScheduleItem], output_dir: Path) -> list[ResolvedScheduleItem]:
    episodes = _discover_episode_outputs(output_dir)
    resolved: list[ResolvedScheduleItem] = []
    missing: list[str] = []

    for item in items:
        slug = episodes.get(item.episode_number)
        source_mode = _source_mode(item.mode)
        if slug is None:
            missing.append(f"episode {item.episode_number} mode {item.mode}")
            continue
        path = output_dir / slug / f"{slug}{MODE_OUTPUT_SUFFIXES[source_mode]}"
        if not path.exists():
            missing.append(f"episode {item.episode_number} mode {item.mode}")
            continue
        resolved.append(
            ResolvedScheduleItem(
                day=item.day,
                episode_number=item.episode_number,
                mode=item.mode,
                source_mode=source_mode,
                emoji=item.emoji,
                slug=slug,
                path=path,
            )
        )

    if missing:
        raise MissingScheduleOutputError(missing)
    return resolved


def _discover_episode_outputs(output_dir: Path) -> dict[int, str]:
    if not output_dir.exists():
        return {}
    return {
        index: path.name
        for index, path in enumerate(sorted(child for child in output_dir.iterdir() if child.is_dir()), start=1)
    }


def _source_mode(mode: int) -> int:
    if mode == 4:
        return 1
    if mode not in MODE_OUTPUT_SUFFIXES:
        raise ValueError(f"Unsupported schedule mode: {mode}")
    return mode
