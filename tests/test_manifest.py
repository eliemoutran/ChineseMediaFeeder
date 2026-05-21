from datetime import datetime
from pathlib import Path

import chinese_media_feeder.manifest as manifest
from chinese_media_feeder.manifest import ManifestStore


def test_manifest_starts_empty_when_file_missing(tmp_path):
    store = ManifestStore(tmp_path / "manifest.json")

    assert store.load() == {"episodes": {}}


def test_manifest_save_writes_formatted_unescaped_json_with_newline(tmp_path):
    store = ManifestStore(tmp_path / "manifest.json")

    store.save({"episodes": {"中文": {"title": "你好"}}})

    content = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert '"你好"' in content
    assert "\\u4f60" not in content
    assert content.endswith("\n")


def test_manifest_updates_episode_step_status(tmp_path):
    store = ManifestStore(tmp_path / "manifest.json")

    store.update_step(
        slug="peppa-001",
        input_path=Path("media/input/peppa-001.mp4"),
        step="transcribe",
        status="complete",
        artifacts={"raw_transcript": Path("media/work/peppa-001/transcript.raw.json")},
        models={"transcribe": "gpt-4o-transcribe-diarize"},
    )

    data = store.load()
    episode = data["episodes"]["peppa-001"]
    assert episode["input_path"] == "media/input/peppa-001.mp4"
    assert episode["steps"]["transcribe"]["status"] == "complete"
    assert episode["artifacts"]["raw_transcript"] == "media/work/peppa-001/transcript.raw.json"
    assert episode["models"]["transcribe"] == "gpt-4o-transcribe-diarize"
    assert "updated_at" in episode


def test_manifest_update_step_stores_outputs_error_and_step_updated_at(tmp_path):
    store = ManifestStore(tmp_path / "manifest.json")

    store.update_step(
        slug="peppa-001",
        input_path=Path("media/input/peppa-001.mp4"),
        step="render",
        status="failed",
        outputs={"mode2": Path("media/output/peppa-001/peppa-001.mode2-pinyin.mp4")},
        error="ffmpeg failed",
    )

    data = store.load()
    episode = data["episodes"]["peppa-001"]
    step = episode["steps"]["render"]
    assert episode["outputs"]["mode2"] == "media/output/peppa-001/peppa-001.mode2-pinyin.mp4"
    assert step["error"] == "ffmpeg failed"
    assert "updated_at" in step


def test_manifest_update_step_clears_previous_error_when_status_changes(tmp_path):
    store = ManifestStore(tmp_path / "manifest.json")
    store.update_step(
        slug="peppa-001",
        input_path=Path("media/input/peppa-001.mp4"),
        step="render",
        status="failed",
        error="ffmpeg failed",
    )

    store.update_step(
        slug="peppa-001",
        input_path=Path("media/input/peppa-001.mp4"),
        step="render",
        status="skipped",
    )

    assert "error" not in store.load()["episodes"]["peppa-001"]["steps"]["render"]


def test_manifest_update_step_uses_one_timezone_aware_timestamp(tmp_path, monkeypatch):
    store = ManifestStore(tmp_path / "manifest.json")
    timestamps = iter(["2026-05-20T10:00:00+00:00", "2026-05-20T10:00:01+00:00"])
    monkeypatch.setattr(manifest, "_now_iso", lambda: next(timestamps))

    store.update_step(
        slug="peppa-001",
        input_path=Path("media/input/peppa-001.mp4"),
        step="render",
        status="complete",
    )

    episode = store.load()["episodes"]["peppa-001"]
    timestamp = episode["updated_at"]
    assert episode["steps"]["render"]["updated_at"] == timestamp
    assert datetime.fromisoformat(timestamp).tzinfo is not None
