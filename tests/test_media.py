from pathlib import Path

from chinese_media_feeder.media import (
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
