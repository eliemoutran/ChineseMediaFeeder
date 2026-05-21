from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from chinese_media_feeder.cues import Cue


DEFAULT_SUBTITLE_LEAD_IN_SECONDS = 0.10
DEFAULT_SUBTITLE_LINGER_SECONDS = 0.15
UNKNOWN_SPEAKERS = {"", "unknown", "unknown_speaker", "speaker_unknown", "none", "null"}


@dataclass(frozen=True)
class SubtitleEvent:
    start: float
    end: float
    text: str


def ass_time(seconds: float) -> str:
    total_hundredths = int(
        (Decimal(str(seconds)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    hundredths = total_hundredths % 100
    total_seconds = total_hundredths // 100
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours}:{mins:02d}:{secs:02d}.{hundredths:02d}"


def escape_ass_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def build_pinyin_events(
    cues: list[Cue],
    lead_in_seconds: float = DEFAULT_SUBTITLE_LEAD_IN_SECONDS,
    linger_seconds: float = DEFAULT_SUBTITLE_LINGER_SECONDS,
) -> list[SubtitleEvent]:
    return _build_subtitle_events(cues, [cue.pinyin or "" for cue in cues], lead_in_seconds, linger_seconds)


def build_alternating_events(
    cues: list[Cue],
    lead_in_seconds: float = DEFAULT_SUBTITLE_LEAD_IN_SECONDS,
    linger_seconds: float = DEFAULT_SUBTITLE_LINGER_SECONDS,
) -> list[SubtitleEvent]:
    current_mode = "pinyin"
    last_speaker: str | None = None
    texts = []

    for cue in cues:
        speaker = _known_speaker(cue.speaker)
        if speaker is not None:
            if last_speaker is not None and speaker != last_speaker:
                current_mode = "english" if current_mode == "pinyin" else "pinyin"
            last_speaker = speaker
        text = cue.pinyin if current_mode == "pinyin" else cue.english
        texts.append(text or "")

    return _build_subtitle_events(cues, texts, lead_in_seconds, linger_seconds)


def render_ass(cues: list[Cue], mode: str = "pinyin") -> str:
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
        "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,3,8,0,2,60,60,54,1",
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


def _build_subtitle_events(
    cues: list[Cue],
    texts: list[str],
    lead_in_seconds: float,
    linger_seconds: float,
) -> list[SubtitleEvent]:
    events: list[SubtitleEvent] = []
    for index, (cue, text) in enumerate(zip(cues, texts, strict=True)):
        start = max(0.0, cue.start - lead_in_seconds)
        if events and start < events[-1].end:
            start = events[-1].end

        end = cue.end + linger_seconds
        if index + 1 < len(cues):
            end = min(end, cues[index + 1].start)
        end = max(start, end)

        events.append(SubtitleEvent(round(start, 3), round(end, 3), text))
    return events


def _known_speaker(speaker: str | None) -> str | None:
    if speaker is None:
        return None
    normalized = speaker.strip().lower()
    if normalized in UNKNOWN_SPEAKERS:
        return None
    return normalized
