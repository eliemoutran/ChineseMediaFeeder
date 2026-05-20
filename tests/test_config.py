from pathlib import Path

from chinese_media_feeder.config import Settings


def test_settings_defaults_are_media_relative(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_TRANSCRIBE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TRANSLATION_MODEL", raising=False)
    monkeypatch.delenv("MEDIA_INPUT_DIR", raising=False)
    monkeypatch.delenv("MEDIA_WORK_DIR", raising=False)
    monkeypatch.delenv("MEDIA_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("MEDIA_MANIFEST_PATH", raising=False)

    settings = Settings.from_env(load_dotenv_file=False)

    assert settings.openai_api_key is None
    assert settings.transcribe_model == "gpt-4o-transcribe-diarize"
    assert settings.translation_model == "gpt-5.4-mini"
    assert settings.input_dir == Path("media/input")
    assert settings.work_dir == Path("media/work")
    assert settings.output_dir == Path("media/output")
    assert settings.manifest_path == Path("media/manifest.json")


def test_settings_reads_environment_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_TRANSCRIBE_MODEL", "transcribe-override")
    monkeypatch.setenv("OPENAI_TRANSLATION_MODEL", "gpt-5.5")
    monkeypatch.setenv("MEDIA_INPUT_DIR", str(tmp_path / "in"))
    monkeypatch.setenv("MEDIA_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("MEDIA_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("MEDIA_MANIFEST_PATH", str(tmp_path / "manifest.json"))

    settings = Settings.from_env(load_dotenv_file=False)

    assert settings.openai_api_key == "sk-test"
    assert settings.transcribe_model == "transcribe-override"
    assert settings.translation_model == "gpt-5.5"
    assert settings.input_dir == tmp_path / "in"
    assert settings.work_dir == tmp_path / "work"
    assert settings.output_dir == tmp_path / "out"
    assert settings.manifest_path == tmp_path / "manifest.json"


def test_settings_loads_dotenv_from_current_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_TRANSCRIBE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TRANSLATION_MODEL", raising=False)
    monkeypatch.delenv("MEDIA_INPUT_DIR", raising=False)
    monkeypatch.delenv("MEDIA_WORK_DIR", raising=False)
    monkeypatch.delenv("MEDIA_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("MEDIA_MANIFEST_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-cwd",
                "OPENAI_TRANSCRIBE_MODEL=cwd-transcribe",
                "OPENAI_TRANSLATION_MODEL=cwd-translate",
                "MEDIA_INPUT_DIR=cwd/input",
                "MEDIA_WORK_DIR=cwd/work",
                "MEDIA_OUTPUT_DIR=cwd/output",
                "MEDIA_MANIFEST_PATH=cwd/manifest.json",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings.from_env()

    assert settings.openai_api_key == "sk-cwd"
    assert settings.transcribe_model == "cwd-transcribe"
    assert settings.translation_model == "cwd-translate"
    assert settings.input_dir == Path("cwd/input")
    assert settings.work_dir == Path("cwd/work")
    assert settings.output_dir == Path("cwd/output")
    assert settings.manifest_path == Path("cwd/manifest.json")


def test_settings_ensure_directories_creates_media_directories(tmp_path):
    settings = Settings(
        openai_api_key=None,
        transcribe_model="transcribe-model",
        translation_model="translation-model",
        input_dir=tmp_path / "input",
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "output",
        manifest_path=tmp_path / "state" / "manifest.json",
    )

    settings.ensure_directories()

    assert settings.input_dir.is_dir()
    assert settings.work_dir.is_dir()
    assert settings.output_dir.is_dir()
    assert settings.manifest_path.parent.is_dir()
