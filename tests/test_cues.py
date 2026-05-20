import json

from chinese_media_feeder.cues import Cue, cue_from_dict, cue_to_dict, normalize_transcript


def test_normalize_transcript_reads_segments_fixture():
    raw = json.loads(open("tests/fixtures/transcript.diarized.json", encoding="utf-8").read())

    cues = normalize_transcript(raw)

    assert cues == [
        Cue(index=1, start=0.4, end=2.1, speaker="SPEAKER_00", chinese="你好，佩奇。"),
        Cue(index=2, start=2.2, end=3.8, speaker="SPEAKER_01", chinese="你好，乔治！"),
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
