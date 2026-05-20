from chinese_media_feeder.cues import Cue
from chinese_media_feeder.subtitles import ass_time, build_alternating_events, escape_ass_text, render_ass


def test_ass_time_formats_hundredths():
    assert ass_time(65.43) == "0:01:05.43"


def test_escape_ass_text_handles_special_characters_and_newlines():
    assert escape_ass_text("a{b}\nc") == "a\\{b\\}\\Nc"


def test_build_alternating_events_switches_between_pinyin_and_english():
    cues = [
        Cue(index=1, start=0, end=1, speaker="A", chinese="你好", pinyin="ni hao", english="Hello"),
        Cue(index=2, start=1, end=2, speaker="B", chinese="再见", pinyin="zai jian", english="Bye"),
        Cue(index=3, start=2, end=3, speaker="A", chinese="来了", pinyin="lai le", english="Coming"),
    ]

    events = build_alternating_events(cues)

    assert [event.text for event in events] == ["ni hao", "Bye", "lai le"]


def test_render_ass_contains_dialogue_lines():
    cues = [
        Cue(index=1, start=0, end=1.5, speaker=None, chinese="你好", pinyin="ni hao", english="Hello"),
    ]

    content = render_ass(cues, mode="pinyin")

    assert "[Script Info]" in content
    assert "Style: Default" in content
    assert "Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,ni hao" in content
