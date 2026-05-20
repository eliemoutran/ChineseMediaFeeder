import json
from pathlib import Path

from chinese_media_feeder.cues import Cue, cue_from_dict, cue_to_dict, normalize_transcript


def test_normalize_transcript_reads_segments_fixture():
    raw = json.loads(Path("tests/fixtures/transcript.diarized.json").read_text(encoding="utf-8"))

    cues = normalize_transcript(raw)

    assert cues == [
        Cue(index=1, start=0.4, end=2.1, speaker="SPEAKER_00", chinese="你好，佩奇。"),
        Cue(index=2, start=2.2, end=3.8, speaker="SPEAKER_01", chinese="你好，乔治！"),
    ]


def test_normalize_transcript_reads_diarized_segments_and_skips_empty_text():
    raw = {
        "diarized_segments": [
            {"start": 0, "end": 1, "transcript": "第一句。", "speaker_label": "SPEAKER_00"},
            {"start": 1, "end": 2, "transcript": "  ", "speaker_label": "SPEAKER_01"},
            {"start": 2, "end": 3, "transcript": "第二句。", "speaker_label": "SPEAKER_02"},
        ]
    }

    cues = normalize_transcript(raw)

    assert cues == [
        Cue(index=1, start=0.0, end=1.0, speaker="SPEAKER_00", chinese="第一句。"),
        Cue(index=2, start=2.0, end=3.0, speaker="SPEAKER_02", chinese="第二句。"),
    ]


def test_cue_round_trip_preserves_optional_learning_fields():
    cue = Cue(
        index=1,
        start=0.0,
        end=1.25,
        speaker="SPEAKER_00",
        chinese="我来了。",
        pinyin="wo lai le.",
        english="I'm coming.",
    )

    assert cue_from_dict(cue_to_dict(cue)) == cue
