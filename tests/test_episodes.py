from pathlib import Path

from chinese_media_feeder.episodes import EpisodePaths, scan_input_videos, slugify_episode


def test_slugify_episode_uses_filename_stem_safely():
    assert slugify_episode(Path("Peppa Pig 001!.mp4")) == "peppa-pig-001"
    assert slugify_episode(Path("  中文 Episode 02.mov")) == "episode-02"


def test_episode_paths_follow_output_contract(tmp_path):
    paths = EpisodePaths.from_input(
        input_path=tmp_path / "input" / "peppa-001.mp4",
        work_root=tmp_path / "work",
        output_root=tmp_path / "output",
    )

    assert paths.slug == "peppa-001"
    assert paths.work_dir == tmp_path / "work" / "peppa-001"
    assert paths.output_dir == tmp_path / "output" / "peppa-001"
    assert paths.audio_path == paths.work_dir / "audio.m4a"
    assert paths.raw_transcript_path == paths.work_dir / "transcript.raw.json"
    assert paths.normalized_cues_path == paths.work_dir / "cues.normalized.json"
    assert paths.pinyin_subtitle_path == paths.work_dir / "subtitles.pinyin.ass"
    assert paths.alternating_subtitle_path == paths.work_dir / "subtitles.alternating.ass"
    assert paths.mode1_path == paths.output_dir / "peppa-001.mode1-nosubs.mp4"
    assert paths.mode2_path == paths.output_dir / "peppa-001.mode2-pinyin.mp4"
    assert paths.mode3_path == paths.output_dir / "peppa-001.mode3-alternating.mp4"


def test_scan_input_videos_returns_supported_files_sorted(tmp_path):
    (tmp_path / "b.mp4").write_text("video")
    (tmp_path / "a.mkv").write_text("video")
    (tmp_path / "notes.txt").write_text("not video")

    assert scan_input_videos(tmp_path) == [tmp_path / "a.mkv", tmp_path / "b.mp4"]
