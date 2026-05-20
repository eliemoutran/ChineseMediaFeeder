import json

from typer.testing import CliRunner

from chinese_media_feeder.cli import app


runner = CliRunner()


def configure_media_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MEDIA_INPUT_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("MEDIA_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("MEDIA_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("MEDIA_MANIFEST_PATH", str(tmp_path / "manifest.json"))


def test_scan_lists_supported_videos(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    video = input_dir / "Peppa 001.mp4"
    video.write_text("video")
    (input_dir / "notes.txt").write_text("ignored")

    result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0
    assert result.output == f"peppa-001\t{video}\n"


def test_status_prints_completed_manifest_steps(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "episodes": {
                    "peppa-001": {
                        "steps": {
                            "extract_audio": {"status": "complete"},
                            "transcribe": {"status": "failed"},
                            "render_mode1": {"status": "complete"},
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert result.output == "peppa-001\textract_audio, render_mode1\n"


def test_process_requires_openai_api_key(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    input_file = tmp_path / "input" / "episode.mp4"
    input_file.parent.mkdir()
    input_file.write_text("video")

    result = runner.invoke(app, ["process", str(input_file)])

    assert result.exit_code != 0
    assert "OPENAI_API_KEY is required for processing." in result.output
