from pathlib import Path

from chinese_media_feeder.manifest import ManifestStore


def test_manifest_starts_empty_when_file_missing(tmp_path):
    store = ManifestStore(tmp_path / "manifest.json")

    assert store.load() == {"episodes": {}}


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
