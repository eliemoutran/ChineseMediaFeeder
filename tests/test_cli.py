import json
import os
from pathlib import Path
import subprocess
import sys

from typer.testing import CliRunner

import chinese_media_feeder.cli as cli_module
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


def test_scan_handles_non_ascii_paths_with_legacy_stdout_encoding(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    video = input_dir / "Peppa Pig 粉红猪小妹 01.mp4"
    video.write_text("video")
    env = cli_subprocess_env(tmp_path)
    env["PYTHONIOENCODING"] = "cp1252"

    result = subprocess.run(
        [sys.executable, "-c", "from chinese_media_feeder.cli import app; app()", "scan"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0
    assert f"peppa-pig-01\t{video}" in result.stdout


def test_module_invocation_runs_cli_scan(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    video = input_dir / "Peppa 001.mp4"
    video.write_text("video")

    result = subprocess.run(
        [sys.executable, "-m", "chinese_media_feeder.cli", "scan"],
        cwd=Path(__file__).resolve().parents[1],
        env=cli_subprocess_env(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == f"peppa-001\t{video}\n"


def cli_subprocess_env(tmp_path):
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = str(repo_root / "src")
    env.pop("OPENAI_API_KEY", None)
    env["MEDIA_INPUT_DIR"] = str(tmp_path / "input")
    env["MEDIA_WORK_DIR"] = str(tmp_path / "work")
    env["MEDIA_OUTPUT_DIR"] = str(tmp_path / "output")
    env["MEDIA_MANIFEST_PATH"] = str(tmp_path / "manifest.json")
    return env


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
    assert result.output == "peppa-001\textract_audio=complete, transcribe=failed, render_mode1=complete\n"


def test_status_prints_failed_step_errors(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "episodes": {
                    "peppa-001": {
                        "steps": {
                            "transcribe": {
                                "status": "failed",
                                "error": "network unavailable",
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert result.output == "peppa-001\ttranscribe=failed(network unavailable)\n"


def test_process_requires_openai_api_key(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    input_file = tmp_path / "input" / "episode.mp4"
    input_file.parent.mkdir()
    input_file.write_text("video")

    result = runner.invoke(app, ["process", str(input_file)])

    assert result.exit_code != 0
    assert "OPENAI_API_KEY is required for processing." in result.output


def test_process_uses_adapter_and_processor_with_force(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    input_file = tmp_path / "input" / "episode.mp4"
    input_file.parent.mkdir()
    input_file.write_text("video")
    calls = {}

    class FakeOpenAIAdapter:
        def __init__(self, api_key, transcribe_model, translation_model):
            calls["adapter"] = (api_key, transcribe_model, translation_model)

    class FakeEpisodeProcessor:
        def __init__(self, settings, openai):
            calls["processor_init"] = (settings, openai)

        def process(self, input_path: Path, force: bool = False):
            calls["process"] = (input_path, force)

            class Paths:
                output_dir = tmp_path / "output" / "episode"

            return Paths()

    monkeypatch.setattr(cli_module, "OpenAIAdapter", FakeOpenAIAdapter)
    monkeypatch.setattr(cli_module, "EpisodeProcessor", FakeEpisodeProcessor)

    result = runner.invoke(app, ["process", str(input_file), "--force"])

    assert result.exit_code == 0
    assert calls["adapter"] == ("sk-test", "gpt-4o-transcribe-diarize", "gpt-5.4-mini")
    assert calls["process"] == (input_file, True)
    assert result.output == f"Generated {tmp_path / 'output' / 'episode'}\n"


def test_process_all_empty_input_succeeds_without_openai_api_key(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)

    result = runner.invoke(app, ["process-all"])

    assert result.exit_code == 0
    assert result.output == f"No supported videos found in {tmp_path / 'input'}\n"


def test_process_all_continues_after_failure_and_exits_nonzero(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    failing_video = input_dir / "01 fail.mp4"
    succeeding_video = input_dir / "02 pass.mp4"
    failing_video.write_text("video")
    succeeding_video.write_text("video")
    processed = []

    class FakeOpenAIAdapter:
        def __init__(self, api_key, transcribe_model, translation_model):
            pass

    class FakeEpisodeProcessor:
        def __init__(self, settings, openai):
            pass

        def process(self, input_path: Path, force: bool = False):
            processed.append((input_path, force))
            if input_path == failing_video:
                raise RuntimeError("render failed")

            class Paths:
                output_dir = tmp_path / "output" / "02-pass"

            return Paths()

    monkeypatch.setattr(cli_module, "OpenAIAdapter", FakeOpenAIAdapter)
    monkeypatch.setattr(cli_module, "EpisodeProcessor", FakeEpisodeProcessor)

    result = runner.invoke(app, ["process-all", "--force"])

    assert result.exit_code == 1
    assert processed == [(failing_video, True), (succeeding_video, True)]
    assert f"Failed {failing_video}: render failed" in result.output
    assert f"Generated {tmp_path / 'output' / '02-pass'}" in result.output
