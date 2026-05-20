from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chinese_media_feeder.cues import Cue


@dataclass(frozen=True)
class SubtitleEvent:
    start: float
    end: float
    text: str


def ass_time(seconds: float) -> str:
    total_hundredths = int(round(seconds * 100))
    hundredths = total_hundredths % 100
    total_seconds = total_hundredths // 100
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours}:{mins:02d}:{secs:02d}.{hundredths:02d}"


def escape_ass_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def build_pinyin_events(cues: list[Cue]) -> list[SubtitleEvent]:
    return [SubtitleEvent(cue.start, cue.end, cue.pinyin or "") for cue in cues]


def build_alternating_events(cues: list[Cue]) -> list[SubtitleEvent]:
    events: list[SubtitleEvent] = []
    for zero_index, cue in enumerate(cues):
        text = cue.pinyin if zero_index % 2 == 0 else cue.english
        events.append(SubtitleEvent(cue.start, cue.end, text or ""))
    return events


def render_ass(cues: list[Cue], mode: str) -> str:
    if mode == "pinyin":
        events = build_pinyin_events(cues)
    elif mode == "alternating":
        events = build_alternating_events(cues)
    else:
        raise ValueError(f"Unsupported subtitle mode: {mode}")

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1280",
        "PlayResY: 720",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,54,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for event in events:
        lines.append(
            f"Dialogue: 0,{ass_time(event.start)},{ass_time(event.end)},Default,,0,0,0,,{escape_ass_text(event.text)}"
        )
    return "\n".join(lines) + "\n"


def write_ass(path: Path, cues: list[Cue], mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ass(cues, mode=mode), encoding="utf-8")
