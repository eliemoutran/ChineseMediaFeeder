import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

from typer.testing import CliRunner

import chinese_media_feeder.cli as cli_module
from chinese_media_feeder.bot import BotStateStore, DryRunTelegramClient, InteractiveDailySender
from chinese_media_feeder.config import Settings
from chinese_media_feeder.cli import app


runner = CliRunner()


def configure_media_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_TRANSCRIBE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TRANSLATION_MODEL", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("MEDIA_INPUT_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("MEDIA_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("MEDIA_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("MEDIA_MANIFEST_PATH", str(tmp_path / "manifest.json"))
    monkeypatch.setenv("BOT_STATE_PATH", str(tmp_path / "bot-state.json"))
    monkeypatch.delenv("BOT_TIMEZONE", raising=False)
    monkeypatch.delenv("BOT_START_TIME", raising=False)
    monkeypatch.delenv("BOT_NUDGE_TIME", raising=False)
    monkeypatch.delenv("BOT_REMINDER_TIME", raising=False)


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
    env.pop("TELEGRAM_BOT_TOKEN", None)
    env.pop("TELEGRAM_CHAT_ID", None)
    env["MEDIA_INPUT_DIR"] = str(tmp_path / "input")
    env["MEDIA_WORK_DIR"] = str(tmp_path / "work")
    env["MEDIA_OUTPUT_DIR"] = str(tmp_path / "output")
    env["MEDIA_MANIFEST_PATH"] = str(tmp_path / "manifest.json")
    env["BOT_STATE_PATH"] = str(tmp_path / "bot-state.json")
    env.pop("BOT_TIMEZONE", None)
    env.pop("BOT_START_TIME", None)
    env.pop("BOT_NUDGE_TIME", None)
    env.pop("BOT_REMINDER_TIME", None)
    return env


def make_output(output_dir: Path, slug: str, suffix: str) -> Path:
    episode_dir = output_dir / slug
    episode_dir.mkdir(parents=True, exist_ok=True)
    path = episode_dir / f"{slug}{suffix}"
    path.write_bytes(b"video")
    return path


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
        def __init__(self, settings, openai, progress_callback=None):
            calls["processor_init"] = (settings, openai)
            calls["progress_callback"] = progress_callback

        def process(self, input_path: Path, force: bool = False):
            calls["process"] = (input_path, force)
            calls["progress_callback"](type("Event", (), {"slug": "episode", "step": "render_mode1", "status": "complete"})())

            class Paths:
                output_dir = tmp_path / "output" / "episode"

            return Paths()

    monkeypatch.setattr(cli_module, "OpenAIAdapter", FakeOpenAIAdapter)
    monkeypatch.setattr(cli_module, "EpisodeProcessor", FakeEpisodeProcessor)

    result = runner.invoke(app, ["process", str(input_file), "--force"])

    assert result.exit_code == 0
    assert calls["adapter"] == ("sk-test", "gpt-4o-transcribe-diarize", "gpt-5.4-mini")
    assert calls["process"] == (input_file, True)
    assert result.output == f"episode\trender_mode1=complete\nGenerated {tmp_path / 'output' / 'episode'}\n"


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
        def __init__(self, settings, openai, progress_callback=None):
            self.progress_callback = progress_callback

        def process(self, input_path: Path, force: bool = False):
            processed.append((input_path, force))
            if input_path == failing_video:
                self.progress_callback(
                    type("Event", (), {"slug": "01-fail", "step": "render_mode1", "status": "failed"})()
                )
                raise RuntimeError("render failed")
            self.progress_callback(
                type("Event", (), {"slug": "02-pass", "step": "render_mode1", "status": "skipped"})()
            )

            class Paths:
                output_dir = tmp_path / "output" / "02-pass"

            return Paths()

    monkeypatch.setattr(cli_module, "OpenAIAdapter", FakeOpenAIAdapter)
    monkeypatch.setattr(cli_module, "EpisodeProcessor", FakeEpisodeProcessor)

    result = runner.invoke(app, ["process-all", "--force"])

    assert result.exit_code == 1
    assert processed == [(failing_video, True), (succeeding_video, True)]
    assert "01-fail\trender_mode1=failed" in result.output
    assert f"Failed {failing_video}: render failed" in result.output
    assert "02-pass\trender_mode1=skipped" in result.output
    assert f"Generated {tmp_path / 'output' / '02-pass'}" in result.output


def test_schedule_preview_lists_resolved_day(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    output = tmp_path / "output"
    video = make_output(output, "peppa-001", ".mode1-nosubs.mp4")

    result = runner.invoke(app, ["schedule", "preview", "--day", "1"])

    assert result.exit_code == 0
    assert result.output == f"Day 1\n📺 ep1.mp4 - Mode 1\t{video}\n"


def test_bot_send_day_dry_run_does_not_require_token(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    output = tmp_path / "output"
    make_output(output, "peppa-001", ".mode1-nosubs.mp4")

    result = runner.invoke(app, ["bot", "send-day", "--day", "1", "--dry-run"])

    assert result.exit_code == 0
    assert result.output == "Sent day 1 (dry-run): 2 messages\n"
    assert not (tmp_path / "bot-state.json").exists()


def test_bot_send_day_requires_telegram_config_without_dry_run(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    output = tmp_path / "output"
    make_output(output, "peppa-001", ".mode1-nosubs.mp4")

    result = runner.invoke(app, ["bot", "send-day", "--day", "1"])

    assert result.exit_code != 0
    assert "TELEGRAM_BOT_TOKEN is required" in result.output


def test_bot_test_sends_message_and_optional_video(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    output = tmp_path / "output"
    video = make_output(output, "peppa-001", ".mode1-nosubs.mp4")
    calls = []

    class FakeTelegramClient:
        def __init__(self, token):
            calls.append(("init", token))

        def send_message(self, chat_id, text):
            calls.append(("message", chat_id, text))
            return {"message_id": 1}

        def send_video(self, chat_id, video_path, caption):
            calls.append(("video", chat_id, video_path, caption))
            return {"message_id": 2}

        def close(self):
            calls.append(("close",))

    monkeypatch.setattr(cli_module, "TelegramClient", FakeTelegramClient)

    result = runner.invoke(app, ["bot", "test", "--with-video"])

    assert result.exit_code == 0
    assert calls == [
        ("init", "token"),
        ("message", "123", "ChineseMediaFeeder bot test"),
        ("video", "123", video, "ChineseMediaFeeder test video"),
        ("close",),
    ]
    assert result.output == "Sent Telegram test message and video\n"


def test_bot_state_reset_and_set_day_commands(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    state_path = tmp_path / "bot-state.json"
    state_path.write_text(
        json.dumps({"completed_days": {"1": {"status": "completed"}}, "active_session": None}),
        encoding="utf-8",
    )

    state = runner.invoke(app, ["bot", "state"])
    reset = runner.invoke(app, ["bot", "reset"])
    set_day = runner.invoke(app, ["bot", "set-day", "--day", "5"])

    assert state.exit_code == 0
    assert "Next learner day: 2" in state.output
    assert reset.exit_code == 0
    assert reset.output == "Bot state reset. Next learner day: 1\n"
    assert set_day.exit_code == 0
    assert set_day.output == "Next learner day set to 5\n"


def test_bot_time_commands_persist_runtime_config(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)

    start = runner.invoke(app, ["bot", "set-start", "--time", "08:15", "--timezone", "Asia/Manila"])
    nudge = runner.invoke(app, ["bot", "set-nudge", "--time", "13:45"])
    reminder = runner.invoke(app, ["bot", "set-reminder", "--time", "21:30"])

    state = json.loads((tmp_path / "bot-state.json").read_text(encoding="utf-8"))
    assert start.exit_code == 0
    assert nudge.exit_code == 0
    assert reminder.exit_code == 0
    assert state["runtime_config"] == {
        "timezone": "Asia/Manila",
        "start_time": "08:15",
        "nudge_time": "13:45",
        "reminder_time": "21:30",
    }


def test_due_checkpoint_late_first_start_does_not_send_immediate_reminders(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    output = tmp_path / "output"
    make_output(output, "peppa-001", ".mode1-nosubs.mp4")
    settings = Settings.from_env(load_dotenv_file=False)
    state = BotStateStore(tmp_path / "bot-state.json")
    telegram = DryRunTelegramClient()
    sender = InteractiveDailySender(output_dir=output, state=state, telegram=telegram, chat_id="123")

    class FixedDateTime:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 5, 22, 14, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(cli_module, "datetime", FixedDateTime)

    cli_module._process_due_checkpoints(settings, sender)

    assert [action["type"] for action in telegram.actions] == ["message", "video"]
    assert state.checkpoint_sent("start", "2026-05-22") is True
    assert state.checkpoint_sent("nudge", "2026-05-22") is True
    assert state.checkpoint_sent("reminder", "2026-05-22") is True


def test_due_checkpoint_dry_run_does_not_persist_state(monkeypatch, tmp_path):
    configure_media_env(monkeypatch, tmp_path)
    output = tmp_path / "output"
    make_output(output, "peppa-001", ".mode1-nosubs.mp4")
    settings = Settings.from_env(load_dotenv_file=False)
    state_path = tmp_path / "bot-state.json"
    state = BotStateStore(state_path)
    telegram = DryRunTelegramClient()
    sender = InteractiveDailySender(output_dir=output, state=state, telegram=telegram, chat_id="123")

    class FixedDateTime:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 5, 22, 14, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(cli_module, "datetime", FixedDateTime)

    cli_module._process_due_checkpoints(settings, sender, dry_run=True)

    assert [action["type"] for action in telegram.actions] == ["message", "video"]
    assert not state_path.exists()


def test_due_checkpoint_missing_outputs_do_not_crash_bot_loop(monkeypatch, tmp_path, capsys):
    configure_media_env(monkeypatch, tmp_path)
    settings = Settings.from_env(load_dotenv_file=False)
    state = BotStateStore(tmp_path / "bot-state.json")
    telegram = DryRunTelegramClient()
    sender = InteractiveDailySender(
        output_dir=tmp_path / "missing-output",
        state=state,
        telegram=telegram,
        chat_id="123",
    )

    class FixedDateTime:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 5, 22, 14, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(cli_module, "datetime", FixedDateTime)

    cli_module._process_due_checkpoints(settings, sender)

    assert "Skipped start: Missing scheduled outputs: episode 1 mode 1" in capsys.readouterr().out
    assert telegram.actions == []
    assert state.current_session() is None
