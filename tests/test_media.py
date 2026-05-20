import shutil
import subprocess
from pathlib import Path, PureWindowsPath

import pytest
import chinese_media_feeder.media as media
from chinese_media_feeder.media import (
    MediaRunner,
    build_burn_subtitles_command,
    build_extract_audio_command,
    build_mode1_command,
)


def test_build_extract_audio_command_compresses_to_m4a():
    command = build_extract_audio_command(Path("in.mp4"), Path("audio.m4a"), bitrate="48k")

    assert command == [
        "ffmpeg",
        "-y",
        "-i",
        "in.mp4",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "48k",
        "audio.m4a",
    ]


def test_build_mode1_command_normalizes_to_h264_mp4():
    command = build_mode1_command(Path("in.mkv"), Path("out.mp4"))

    assert command == [
        "ffmpeg",
        "-y",
        "-i",
        "in.mkv",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        "out.mp4",
    ]


def test_build_burn_subtitles_command_uses_ass_filter():
    command = build_burn_subtitles_command(Path("in.mp4"), Path("subs.ass"), Path("out.mp4"))

    assert command == [
        "ffmpeg",
        "-y",
        "-i",
        "in.mp4",
        "-vf",
        "ass=subs.ass",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        "out.mp4",
    ]


def test_build_burn_subtitles_command_escapes_ass_filter_path_with_spaces():
    command = build_burn_subtitles_command(
        Path("in.mp4"),
        Path("media/work/episode one/subtitles.pinyin.ass"),
        Path("out.mp4"),
    )

    assert command[5] == "ass=media/work/episode one/subtitles.pinyin.ass"


def test_build_burn_subtitles_command_escapes_windows_ass_filter_path():
    command = build_burn_subtitles_command(
        Path("in.mp4"),
        PureWindowsPath("C:/Users/Bishop/media work/subs.ass"),
        Path("out.mp4"),
    )

    assert command[5] == "ass=C\\\\:/Users/Bishop/media work/subs.ass"


def test_build_burn_subtitles_command_escapes_filter_metacharacters():
    command = build_burn_subtitles_command(
        Path("in.mp4"),
        Path("subs[forced],v2;director.ass"),
        Path("out.mp4"),
    )

    assert command[5] == "ass=subs\\[forced\\]\\,v2\\;director.ass"


def test_build_burn_subtitles_command_rejects_apostrophe_paths():
    with pytest.raises(ValueError, match="apostrophe"):
        build_burn_subtitles_command(
            Path("in.mp4"),
            Path("director's.ass"),
            Path("out.mp4"),
        )


def test_burn_subtitles_filter_path_smoke_with_ffmpeg(tmp_path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not installed")

    subtitle_dir = tmp_path / "episode one"
    subtitle_dir.mkdir()
    subtitle_path = subtitle_dir / "subs[forced],v2;director.ass"
    subtitle_path.write_text(
        "\n".join(
            [
                "[Script Info]",
                "ScriptType: v4.00+",
                "PlayResX: 320",
                "PlayResY: 240",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1",
                "",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
                "Dialogue: 0,0:00:00.00,0:00:00.10,Default,,0,0,0,,Smoke",
                "",
            ]
        ),
        encoding="utf-8",
    )
    ass_filter = build_burn_subtitles_command(
        Path("in.mp4"),
        subtitle_path,
        Path("out.mp4"),
    )[5]

    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=320x240:d=0.1",
            "-vf",
            ass_filter,
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        check=True,
    )


def test_media_runner_extract_audio_creates_parent_and_runs_builder_command(
    tmp_path, monkeypatch
):
    calls = []
    command = ["ffmpeg", "extract"]

    def fake_build_extract_audio_command(input_path, output_path, bitrate="48k"):
        calls.append(("builder", input_path, output_path, bitrate))
        return command

    def fake_run(command_arg, check):
        calls.append(("run", command_arg, check))

    monkeypatch.setattr(media, "build_extract_audio_command", fake_build_extract_audio_command)
    monkeypatch.setattr(media.subprocess, "run", fake_run)

    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "audio" / "episode" / "audio.m4a"

    MediaRunner().extract_audio(input_path, output_path, bitrate="64k")

    assert output_path.parent.is_dir()
    assert calls == [
        ("builder", input_path, output_path, "64k"),
        ("run", command, True),
    ]


def test_media_runner_render_mode1_creates_parent_and_runs_builder_command(
    tmp_path, monkeypatch
):
    calls = []
    command = ["ffmpeg", "mode1"]

    def fake_build_mode1_command(input_path, output_path):
        calls.append(("builder", input_path, output_path))
        return command

    def fake_run(command_arg, check):
        calls.append(("run", command_arg, check))

    monkeypatch.setattr(media, "build_mode1_command", fake_build_mode1_command)
    monkeypatch.setattr(media.subprocess, "run", fake_run)

    input_path = tmp_path / "input.mkv"
    output_path = tmp_path / "output" / "episode" / "out.mp4"

    MediaRunner().render_mode1(input_path, output_path)

    assert output_path.parent.is_dir()
    assert calls == [
        ("builder", input_path, output_path),
        ("run", command, True),
    ]


def test_media_runner_burn_subtitles_creates_parent_and_runs_builder_command(
    tmp_path, monkeypatch
):
    calls = []
    command = ["ffmpeg", "burn"]

    def fake_build_burn_subtitles_command(input_path, subtitle_path, output_path):
        calls.append(("builder", input_path, subtitle_path, output_path))
        return command

    def fake_run(command_arg, check):
        calls.append(("run", command_arg, check))

    monkeypatch.setattr(media, "build_burn_subtitles_command", fake_build_burn_subtitles_command)
    monkeypatch.setattr(media.subprocess, "run", fake_run)

    input_path = tmp_path / "input.mp4"
    subtitle_path = tmp_path / "subs.ass"
    output_path = tmp_path / "rendered" / "episode" / "out.mp4"

    MediaRunner().burn_subtitles(input_path, subtitle_path, output_path)

    assert output_path.parent.is_dir()
    assert calls == [
        ("builder", input_path, subtitle_path, output_path),
        ("run", command, True),
    ]
