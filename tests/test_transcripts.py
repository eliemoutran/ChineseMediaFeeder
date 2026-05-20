from chinese_media_feeder.transcripts import build_timing_primary_transcript


def test_build_timing_primary_transcript_uses_timing_segments_as_cue_source():
    timing = {
        "segments": [
            {"start": 10.0, "end": 11.2, "text": "你好，佩奇。"},
            {"start": 12.0, "end": 13.0, "text": "我来了。"},
        ]
    }
    diarized = {
        "diarized_segments": [
            {"start": 9.8, "end": 11.4, "speaker": "SPEAKER_00", "text": "你好佩奇"},
            {"start": 20.0, "end": 21.0, "speaker": "SPEAKER_01", "text": "没匹配上"},
        ]
    }

    transcript = build_timing_primary_transcript(timing, diarized)

    assert transcript["source"] == "timing_primary"
    assert transcript["segments"] == [
        {
            "start": 10.0,
            "end": 11.2,
            "text": "你好，佩奇。",
            "speaker": "SPEAKER_00",
            "diarized_text": "你好佩奇",
        },
        {"start": 12.0, "end": 13.0, "text": "我来了。"},
    ]
    assert transcript["timing_transcript"] == timing
    assert transcript["diarized_transcript"] == diarized
    assert transcript["qa"]["unmatched_diarized_segments"] == [
        {"start": 20.0, "end": 21.0, "speaker": "SPEAKER_01", "text": "没匹配上"}
    ]


def test_build_timing_primary_transcript_ignores_diarized_text_for_cue_text():
    timing = {"segments": [{"start": 66.1, "end": 67.4, "text": "短句"}]}
    diarized = {
        "diarized_segments": [
            {
                "start": 60.0,
                "end": 90.0,
                "speaker": "SPEAKER_00",
                "text": "这是一段很长而且时间不可信的转写",
            }
        ]
    }

    transcript = build_timing_primary_transcript(timing, diarized)

    assert transcript["segments"][0]["start"] == 66.1
    assert transcript["segments"][0]["end"] == 67.4
    assert transcript["segments"][0]["text"] == "短句"
    assert transcript["segments"][0]["speaker"] == "SPEAKER_00"
    assert transcript["qa"]["suspicious_diarized_segments"] == [
        {
            "start": 60.0,
            "end": 90.0,
            "speaker": "SPEAKER_00",
            "text": "这是一段很长而且时间不可信的转写",
            "reason": "duration_long_for_text",
        }
    ]
