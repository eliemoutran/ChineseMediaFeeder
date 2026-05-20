from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MAX_CUE_CHARS = 12
HARD_BREAK_PUNCTUATION = set("。！？!?")
SOFT_BREAK_PUNCTUATION = set("，,；;、：:")


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
    for segment in segments:
        text = str(segment.get("text") or segment.get("transcript") or "").strip()
        if not text:
            continue
        start = float(segment["start"])
        end = float(segment["end"])
        speaker = segment.get("speaker") or segment.get("speaker_label")
        pieces = split_subtitle_text(text)
        for piece, piece_start, piece_end in _allocate_piece_times(pieces, start, end):
            cues.append(
                Cue(
                    index=len(cues) + 1,
                    start=piece_start,
                    end=piece_end,
                    speaker=speaker,
                    chinese=piece,
                )
            )
    return cues


def split_subtitle_text(text: str, max_chars: int = MAX_CUE_CHARS) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    pieces: list[str] = []
    for sentence in _split_after_punctuation(stripped, HARD_BREAK_PUNCTUATION):
        if _display_len(sentence) <= max_chars and not _has_space(sentence):
            pieces.append(sentence)
            continue
        pieces.extend(_split_long_sentence(sentence, max_chars))
    return pieces


def _split_after_punctuation(text: str, punctuation: set[str]) -> list[str]:
    pieces: list[str] = []
    current: list[str] = []
    for char in text:
        current.append(char)
        if char in punctuation:
            piece = "".join(current).strip()
            if piece:
                pieces.append(piece)
            current = []
    tail = "".join(current).strip()
    if tail:
        pieces.append(tail)
    return pieces


def _split_long_sentence(text: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    current: list[str] = []
    for char in text:
        current.append(char)
        piece = "".join(current).strip()
        if char.isspace() or char in SOFT_BREAK_PUNCTUATION or _display_len(piece) >= max_chars:
            if piece:
                pieces.append(piece)
            current = []
    tail = "".join(current).strip()
    if tail:
        pieces.append(tail)
    return pieces


def _allocate_piece_times(pieces: list[str], start: float, end: float) -> list[tuple[str, float, float]]:
    if not pieces:
        return []
    duration = max(0.0, end - start)
    weights = [_timing_weight(piece) for piece in pieces]
    total_weight = sum(weights) or len(pieces)
    timed: list[tuple[str, float, float]] = []
    cursor = start
    for index, piece in enumerate(pieces):
        piece_start = cursor
        if index == len(pieces) - 1:
            piece_end = end
        else:
            cursor = round(cursor + duration * (weights[index] / total_weight), 2)
            piece_end = cursor
        timed.append((piece, round(piece_start, 2), round(piece_end, 2)))
    return timed


def _timing_weight(text: str) -> int:
    stripped = text.strip()
    if stripped and stripped[-1] in HARD_BREAK_PUNCTUATION:
        stripped = stripped[:-1]
    return max(1, _display_len(stripped))


def _display_len(text: str) -> int:
    return len("".join(text.split()))


def _has_space(text: str) -> bool:
    return any(char.isspace() for char in text)


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
