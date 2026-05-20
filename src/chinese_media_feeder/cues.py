from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Cue:
    index: int
    start: float
    end: float
    speaker: str | None
    chinese: str
    pinyin: str | None = None
    english: str | None = None


def normalize_transcript(raw: dict[str, Any]) -> list[Cue]:
    segments = raw.get("segments") or raw.get("diarized_segments") or []
    cues: list[Cue] = []
    for offset, segment in enumerate(segments, start=1):
        text = str(segment.get("text") or segment.get("transcript") or "").strip()
        if not text:
            continue
        cues.append(
            Cue(
                index=len(cues) + 1,
                start=float(segment["start"]),
                end=float(segment["end"]),
                speaker=segment.get("speaker") or segment.get("speaker_label"),
                chinese=text,
            )
        )
    return cues


def cue_to_dict(cue: Cue) -> dict[str, Any]:
    return {
        "index": cue.index,
        "start": cue.start,
        "end": cue.end,
        "speaker": cue.speaker,
        "chinese": cue.chinese,
        "pinyin": cue.pinyin,
        "english": cue.english,
    }


def cue_from_dict(data: dict[str, Any]) -> Cue:
    return Cue(
        index=int(data["index"]),
        start=float(data["start"]),
        end=float(data["end"]),
        speaker=data.get("speaker"),
        chinese=str(data["chinese"]),
        pinyin=data.get("pinyin"),
        english=data.get("english"),
    )
