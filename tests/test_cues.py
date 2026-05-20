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


def test_normalize_transcript_splits_long_sentence_on_soft_punctuation():
    raw = {
        "segments": [
            {
                "start": 0,
                "end": 6,
                "speaker": "SPEAKER_00",
                "text": "\u6211\u4eec\u4eca\u5929\u8981\u53bb\u516c\u56ed\uff0c\u770b\u770b\u82b1\u8349\uff0c\u5750\u5c0f\u706b\u8f66\u3002",
            }
        ]
    }

    cues = normalize_transcript(raw)

    assert [cue.chinese for cue in cues] == [
        "\u6211\u4eec\u4eca\u5929\u8981\u53bb\u516c\u56ed\uff0c",
        "\u770b\u770b\u82b1\u8349\uff0c",
        "\u5750\u5c0f\u706b\u8f66\u3002",
    ]
    assert [(cue.start, cue.end) for cue in cues] == [(0.0, 3.0), (3.0, 4.67), (4.67, 6.0)]
    assert [cue.index for cue in cues] == [1, 2, 3]


def test_normalize_transcript_splits_long_text_without_punctuation():
    raw = {
        "segments": [
            {
                "start": 0,
                "end": 4,
                "speaker": "SPEAKER_00",
                "text": "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341",
            }
        ]
    }

    cues = normalize_transcript(raw)

    assert [cue.chinese for cue in cues] == [
        "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u4e00\u4e8c",
        "\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341",
    ]
    assert [(cue.start, cue.end) for cue in cues] == [(0.0, 2.4), (2.4, 4.0)]


def test_normalize_transcript_splits_long_text_on_spaces():
    raw = {
        "segments": [
            {
                "start": 0,
                "end": 4,
                "speaker": "SPEAKER_00",
                "text": "\u6211\u662f\u4f69\u5947 \u8fd9\u662f\u6211\u7684\u5f1f\u5f1f\u4e54\u6cbb",
            }
        ]
    }

    cues = normalize_transcript(raw)

    assert [cue.chinese for cue in cues] == [
        "\u6211\u662f\u4f69\u5947",
        "\u8fd9\u662f\u6211\u7684\u5f1f\u5f1f\u4e54\u6cbb",
    ]
    assert [(cue.start, cue.end) for cue in cues] == [(0.0, 1.33), (1.33, 4.0)]


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
