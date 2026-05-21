import pytest

from chinese_media_feeder.cues import Cue
from chinese_media_feeder.subtitles import (
    ass_time,
    build_alternating_events,
    build_pinyin_events,
    escape_ass_text,
    render_ass,
    write_ass,
)


def test_ass_time_formats_hundredths():
    assert ass_time(65.43) == "0:01:05.43"


def test_ass_time_rounds_half_up_to_hundredths():
    assert ass_time(0.005) == "0:00:00.01"
    assert ass_time(59.995) == "0:01:00.00"
    assert ass_time(3599.995) == "1:00:00.00"


def test_escape_ass_text_handles_special_characters_and_newlines():
    assert escape_ass_text("a{b}\nc") == "a\\{b\\}\\Nc"


def test_escape_ass_text_handles_literal_backslashes_and_braces():
    assert escape_ass_text(r"C:\tmp\{x}") == "C:\\\\tmp\\\\\\{x\\}"


def test_build_alternating_events_switches_between_pinyin_and_english():
    cues = [
        Cue(index=1, start=0, end=1, speaker="A", chinese="你好", pinyin="ni hao", english="Hello"),
        Cue(index=2, start=1, end=2, speaker="B", chinese="再见", pinyin="zai jian", english="Bye"),
        Cue(index=3, start=2, end=3, speaker="A", chinese="来了", pinyin="lai le", english="Coming"),
    ]

    events = build_alternating_events(cues)

    assert [event.text for event in events] == ["ni hao", "Bye", "lai le"]


def test_build_alternating_events_flips_only_on_speaker_change_and_inherits_unknown_speakers():
    cues = [
        Cue(index=1, start=0, end=1, speaker="A", chinese="1", pinyin="p1", english="e1"),
        Cue(index=2, start=1, end=2, speaker="A", chinese="2", pinyin="p2", english="e2"),
        Cue(index=3, start=2, end=3, speaker="B", chinese="3", pinyin="p3", english="e3"),
        Cue(index=4, start=3, end=4, speaker=None, chinese="4", pinyin="p4", english="e4"),
        Cue(index=5, start=4, end=5, speaker="unknown", chinese="5", pinyin="p5", english="e5"),
        Cue(index=6, start=5, end=6, speaker="A", chinese="6", pinyin="p6", english="e6"),
    ]

    events = build_alternating_events(cues)

    assert [event.text for event in events] == ["p1", "p2", "e3", "e4", "e5", "p6"]


def test_build_alternating_events_skips_missing_english_slot():
    cues = [
        Cue(index=1, start=0, end=1, speaker="A", chinese="你好", pinyin="ni hao", english="Hello"),
        Cue(index=2, start=1, end=2, speaker="B", chinese="再见", pinyin="zai jian", english=None),
    ]

    events = build_alternating_events(cues)

    assert [event.text for event in events] == ["ni hao"]


def test_build_pinyin_events_uses_pinyin_and_skips_missing_pinyin():
    cues = [
        Cue(index=1, start=0, end=1, speaker=None, chinese="你好", pinyin="ni hao", english="Hello"),
        Cue(index=2, start=1, end=2, speaker=None, chinese="再见", pinyin=None, english="Bye"),
    ]

    events = build_pinyin_events(cues)

    assert [event.text for event in events] == ["ni hao"]


def test_build_pinyin_events_removes_display_punctuation_and_skips_punctuation_only_cues():
    cues = [
        Cue(index=1, start=0, end=1, speaker=None, chinese="1", pinyin="ni hao.", english=None),
        Cue(index=2, start=1, end=2, speaker=None, chinese="2", pinyin=".", english=None),
        Cue(index=3, start=2, end=3, speaker=None, chinese="3", pinyin="hao, ma?", english=None),
    ]

    events = build_pinyin_events(cues)

    assert [event.text for event in events] == ["ni hao", "hao ma"]


def test_build_alternating_events_removes_display_punctuation_from_english_slots():
    cues = [
        Cue(index=1, start=0, end=1, speaker="A", chinese="1", pinyin="ni hao.", english="Hello."),
        Cue(index=2, start=1, end=2, speaker="B", chinese="2", pinyin="zai jian.", english="Bye!"),
    ]

    events = build_alternating_events(cues)

    assert [event.text for event in events] == ["ni hao", "Bye"]


def test_build_pinyin_events_pads_display_timing_without_overlapping_next_cue():
    cues = [
        Cue(index=1, start=1.0, end=2.0, speaker=None, chinese="1", pinyin="p1", english=None),
        Cue(index=2, start=2.05, end=3.0, speaker=None, chinese="2", pinyin="p2", english=None),
    ]

    events = build_pinyin_events(cues)

    assert [(event.start, event.end) for event in events] == [(0.9, 2.05), (2.05, 3.15)]


def test_render_ass_contains_dialogue_lines():
    cues = [
        Cue(index=1, start=0, end=1.5, speaker=None, chinese="你好", pinyin="ni hao", english="Hello"),
    ]

    content = render_ass(cues, mode="pinyin")

    assert "[Script Info]" in content
    assert "Style: Default" in content
    assert "Dialogue: 0,0:00:00.00,0:00:01.65,Default,,0,0,0,,ni hao" in content


def test_render_ass_uses_boxed_subtitle_background():
    content = render_ass([], mode="pinyin")

    assert (
        "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,"
        "&H80000000,0,0,0,0,100,100,0,0,3,8,0,2,60,60,54,1"
    ) in content


def test_render_ass_defaults_to_pinyin_mode():
    cues = [
        Cue(index=1, start=0, end=1.5, speaker=None, chinese="你好", pinyin="ni hao", english="Hello"),
    ]

    content = render_ass(cues)

    assert "Dialogue: 0,0:00:00.00,0:00:01.65,Default,,0,0,0,,ni hao" in content


def test_render_ass_rejects_unsupported_mode():
    with pytest.raises(ValueError, match="Unsupported subtitle mode: unsupported"):
        render_ass([], mode="unsupported")


def test_write_ass_creates_parent_dirs_and_writes_utf8_content(tmp_path):
    path = tmp_path / "nested" / "subtitles" / "episode.ass"
    cues = [
        Cue(index=1, start=0, end=1.5, speaker=None, chinese="你好", pinyin="nǐ hǎo", english="Hello"),
    ]

    write_ass(path, cues, mode="pinyin")

    assert path.read_text(encoding="utf-8").endswith("Default,,0,0,0,,nǐ hǎo\n")
