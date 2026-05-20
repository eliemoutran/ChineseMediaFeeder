from pathlib import Path

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
