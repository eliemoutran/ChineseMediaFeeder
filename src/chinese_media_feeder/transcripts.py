from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


def build_timing_primary_transcript(timing_transcript: dict[str, Any], diarized_transcript: dict[str, Any]) -> dict[str, Any]:
    diarized_segments = _read_segments(diarized_transcript)
    matched_diarized_indexes: set[int] = set()
    segments: list[dict[str, Any]] = []

    for timing_segment in _read_segments(timing_transcript):
        text = _segment_text(timing_segment)
        if not text:
            continue

        segment = {
            "start": _segment_start(timing_segment),
            "end": _segment_end(timing_segment),
            "text": text,
        }
        match = _best_diarized_match(timing_segment, diarized_segments)
        if match is not None:
            matched_diarized_indexes.add(match[0])
            speaker = match[1].get("speaker") or match[1].get("speaker_label")
            diarized_text = _segment_text(match[1])
            if speaker:
                segment["speaker"] = speaker
            if diarized_text:
                segment["diarized_text"] = diarized_text
        segments.append(segment)

    return {
        "source": "timing_primary",
        "segments": segments,
        "timing_transcript": timing_transcript,
        "diarized_transcript": diarized_transcript,
        "qa": {
            "unmatched_diarized_segments": [
                _public_segment(segment)
                for index, segment in enumerate(diarized_segments)
                if index not in matched_diarized_indexes
            ],
            "suspicious_diarized_segments": [
                {
                    **_public_segment(segment),
                    "reason": "duration_long_for_text",
                }
                for segment in diarized_segments
                if _is_duration_long_for_text(segment)
            ],
        },
    }


def _best_diarized_match(
    timing_segment: dict[str, Any], diarized_segments: list[dict[str, Any]]
) -> tuple[int, dict[str, Any]] | None:
    best: tuple[float, int, dict[str, Any]] | None = None
    timing_text = _segment_text(timing_segment)
    for index, diarized_segment in enumerate(diarized_segments):
        overlap_ratio = _overlap_ratio(timing_segment, diarized_segment)
        if overlap_ratio <= 0:
            continue
        similarity = _text_similarity(timing_text, _segment_text(diarized_segment))
        score = overlap_ratio + similarity * 0.2
        if best is None or score > best[0]:
            best = (score, index, diarized_segment)

    if best is None:
        return None

    candidate = best[2]
    overlap_ratio = _overlap_ratio(timing_segment, candidate)
    similarity = _text_similarity(timing_text, _segment_text(candidate))
    if overlap_ratio >= 0.35 or (overlap_ratio >= 0.15 and similarity >= 0.35):
        return best[1], candidate
    return None


def _read_segments(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    raw_segments = transcript.get("segments") or transcript.get("diarized_segments") or []
    return [segment for segment in raw_segments if isinstance(segment, dict)]


def _public_segment(segment: dict[str, Any]) -> dict[str, Any]:
    public = {
        "start": _segment_start(segment),
        "end": _segment_end(segment),
    }
    speaker = segment.get("speaker") or segment.get("speaker_label")
    text = _segment_text(segment)
    if speaker:
        public["speaker"] = speaker
    if text:
        public["text"] = text
    return public


def _overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
    overlap = min(_segment_end(left), _segment_end(right)) - max(_segment_start(left), _segment_start(right))
    if overlap <= 0:
        return 0.0
    return overlap / max(0.01, min(_segment_duration(left), _segment_duration(right)))


def _text_similarity(left: str, right: str) -> float:
    left_clean = _normalize_text(left)
    right_clean = _normalize_text(right)
    if not left_clean or not right_clean:
        return 0.0
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def _normalize_text(text: str) -> str:
    return "".join(char for char in text.casefold() if char.isalnum())


def _is_duration_long_for_text(segment: dict[str, Any]) -> bool:
    text = _segment_text(segment)
    if not text:
        return False
    return _segment_duration(segment) > _expected_spoken_duration(text) * 2.5


def _expected_spoken_duration(text: str) -> float:
    return min(6.0, max(1.2, len("".join(text.split())) * 0.28 + 0.5))


def _segment_text(segment: dict[str, Any]) -> str:
    return str(segment.get("text") or segment.get("transcript") or "").strip()


def _segment_start(segment: dict[str, Any]) -> float:
    return float(segment["start"])


def _segment_end(segment: dict[str, Any]) -> float:
    return float(segment["end"])


def _segment_duration(segment: dict[str, Any]) -> float:
    return max(0.0, _segment_end(segment) - _segment_start(segment))
