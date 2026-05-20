# V1 Media Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that turns local Mandarin episode videos into no-subtitle, pinyin-subtitle, and alternating pinyin/English MP4 variants.

**Architecture:** Use a small Python package with focused modules for configuration, episode paths, manifest state, OpenAI access, cue normalization, pinyin generation, ASS subtitle writing, ffmpeg media operations, and CLI orchestration. Keep paid API calls behind explicit processing commands and test the core pipeline with fixtures and injected fakes.

**Tech Stack:** Python 3.11+, Typer, Pydantic-free dataclasses, OpenAI Python SDK, pypinyin, python-dotenv, pytest, ffmpeg, Docker.

---

## File Structure

- Create `pyproject.toml`: package metadata, runtime dependencies, pytest config, `cmf` console script.
- Create `.gitignore`: ignores media artifacts, caches, environment files, and virtual environments.
- Create `.env.example`: documented environment variables without secrets.
- Create `README.md`: quick setup and command reference for V1.
- Create `src/chinese_media_feeder/__init__.py`: package version.
- Create `src/chinese_media_feeder/config.py`: environment loading and directory defaults.
- Create `src/chinese_media_feeder/episodes.py`: input scanning, slug generation, and episode path construction.
- Create `src/chinese_media_feeder/manifest.py`: JSON manifest read/write and per-step status updates.
- Create `src/chinese_media_feeder/cues.py`: internal `Cue` model and transcript normalization.
- Create `src/chinese_media_feeder/pinyin.py`: Mandarin text to tone-mark pinyin conversion.
- Create `src/chinese_media_feeder/subtitles.py`: ASS subtitle escaping, style generation, pinyin and alternating subtitle files.
- Create `src/chinese_media_feeder/media.py`: ffmpeg command construction and subprocess execution.
- Create `src/chinese_media_feeder/openai_client.py`: transcription and translation API adapter.
- Create `src/chinese_media_feeder/pipeline.py`: resumable episode processing orchestration.
- Create `src/chinese_media_feeder/cli.py`: `cmf scan`, `cmf process`, `cmf process-all`, and `cmf status`.
- Create `tests/fixtures/transcript.diarized.json`: local transcript fixture with two speakers.
- Create `tests/test_config.py`: config defaults and env overrides.
- Create `tests/test_episodes.py`: slug generation, scanning, and path contract.
- Create `tests/test_manifest.py`: manifest persistence and status transitions.
- Create `tests/test_cues.py`: diarized transcript normalization.
- Create `tests/test_pinyin.py`: pinyin conversion.
- Create `tests/test_subtitles.py`: ASS escaping and Mode 3 alternation.
- Create `tests/test_media.py`: ffmpeg command construction.
- Create `tests/test_pipeline.py`: pipeline orchestration using fake OpenAI and fake ffmpeg.
- Create `Dockerfile`: image with Python package and ffmpeg.
- Create `docker-compose.yml`: mounted media volume and environment file.

---

### Task 1: Project Skeleton and Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `src/chinese_media_feeder/__init__.py`
- Create: `src/chinese_media_feeder/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing config tests**

Create `tests/test_config.py`:

```python
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

    settings = Settings.from_env()

    assert settings.openai_api_key is None
    assert settings.transcribe_model == "gpt-4o-transcribe-diarize"
    assert settings.translation_model == "gpt-5.4-mini"
    assert settings.input_dir == Path("media/input")
    assert settings.work_dir == Path("media/work")
    assert settings.output_dir == Path("media/output")
    assert settings.manifest_path == Path("media/manifest.json")


def test_settings_reads_environment_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe-diarize")
    monkeypatch.setenv("OPENAI_TRANSLATION_MODEL", "gpt-5.5")
    monkeypatch.setenv("MEDIA_INPUT_DIR", str(tmp_path / "in"))
    monkeypatch.setenv("MEDIA_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("MEDIA_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("MEDIA_MANIFEST_PATH", str(tmp_path / "manifest.json"))

    settings = Settings.from_env()

    assert settings.openai_api_key == "sk-test"
    assert settings.translation_model == "gpt-5.5"
    assert settings.input_dir == tmp_path / "in"
    assert settings.work_dir == tmp_path / "work"
    assert settings.output_dir == tmp_path / "out"
    assert settings.manifest_path == tmp_path / "manifest.json"
```

- [ ] **Step 2: Run the config tests to verify they fail**

Run: `pytest tests/test_config.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'chinese_media_feeder'`.

- [ ] **Step 3: Add project metadata and configuration implementation**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "chinese-media-feeder"
version = "0.1.0"
description = "Generate learner-focused Mandarin episode video variants."
requires-python = ">=3.11"
dependencies = [
  "openai>=1.0.0",
  "pypinyin>=0.51.0",
  "python-dotenv>=1.0.0",
  "typer>=0.12.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
]

[project.scripts]
cmf = "chinese_media_feeder.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
*.pyc
media/input/*
media/work/*
media/output/*
media/manifest.json
!media/input/.gitkeep
!media/work/.gitkeep
!media/output/.gitkeep
```

Create `.env.example`:

```text
OPENAI_API_KEY=
OPENAI_TRANSCRIBE_MODEL=gpt-4o-transcribe-diarize
OPENAI_TRANSLATION_MODEL=gpt-5.4-mini
MEDIA_INPUT_DIR=media/input
MEDIA_WORK_DIR=media/work
MEDIA_OUTPUT_DIR=media/output
MEDIA_MANIFEST_PATH=media/manifest.json
```

Create `README.md`:

```markdown
# ChineseMediaFeeder

V1 generates three MP4 variants from local Mandarin episode files:

- Mode 1: no subtitles
- Mode 2: pinyin subtitles
- Mode 3: alternating pinyin and English subtitles

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

## Commands

```bash
cmf scan
cmf process media/input/episode-001.mp4
cmf process-all
cmf status
```
```

Create `src/chinese_media_feeder/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/chinese_media_feeder/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    transcribe_model: str
    translation_model: str
    input_dir: Path
    work_dir: Path
    output_dir: Path
    manifest_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            transcribe_model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe-diarize"),
            translation_model=os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-5.4-mini"),
            input_dir=Path(os.getenv("MEDIA_INPUT_DIR", "media/input")),
            work_dir=Path(os.getenv("MEDIA_WORK_DIR", "media/work")),
            output_dir=Path(os.getenv("MEDIA_OUTPUT_DIR", "media/output")),
            manifest_path=Path(os.getenv("MEDIA_MANIFEST_PATH", "media/manifest.json")),
        )

    def ensure_directories(self) -> None:
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run the config tests to verify they pass**

Run: `pytest tests/test_config.py -v`

Expected: PASS with `2 passed`.

- [ ] **Step 5: Commit the skeleton**

```bash
git add pyproject.toml .gitignore .env.example README.md src/chinese_media_feeder/__init__.py src/chinese_media_feeder/config.py tests/test_config.py
git commit -m "feat: add project skeleton and config"
```

---

### Task 2: Episode Paths and Manifest State

**Files:**
- Create: `src/chinese_media_feeder/episodes.py`
- Create: `src/chinese_media_feeder/manifest.py`
- Test: `tests/test_episodes.py`
- Test: `tests/test_manifest.py`

- [ ] **Step 1: Write failing episode path tests**

Create `tests/test_episodes.py`:

```python
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
```

- [ ] **Step 2: Write failing manifest tests**

Create `tests/test_manifest.py`:

```python
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
```

- [ ] **Step 3: Run the episode and manifest tests to verify they fail**

Run: `pytest tests/test_episodes.py tests/test_manifest.py -v`

Expected: FAIL with import errors for `chinese_media_feeder.episodes` and `chinese_media_feeder.manifest`.

- [ ] **Step 4: Implement episode paths**

Create `src/chinese_media_feeder/episodes.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".m4v", ".webm"}


def slugify_episode(path: Path) -> str:
    ascii_stem = path.stem.encode("ascii", errors="ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_stem).strip("-").lower()
    return slug or "episode"


@dataclass(frozen=True)
class EpisodePaths:
    slug: str
    input_path: Path
    work_dir: Path
    output_dir: Path
    audio_path: Path
    raw_transcript_path: Path
    normalized_cues_path: Path
    pinyin_subtitle_path: Path
    alternating_subtitle_path: Path
    mode1_path: Path
    mode2_path: Path
    mode3_path: Path

    @classmethod
    def from_input(cls, input_path: Path, work_root: Path, output_root: Path) -> "EpisodePaths":
        slug = slugify_episode(input_path)
        work_dir = work_root / slug
        output_dir = output_root / slug
        return cls(
            slug=slug,
            input_path=input_path,
            work_dir=work_dir,
            output_dir=output_dir,
            audio_path=work_dir / "audio.m4a",
            raw_transcript_path=work_dir / "transcript.raw.json",
            normalized_cues_path=work_dir / "cues.normalized.json",
            pinyin_subtitle_path=work_dir / "subtitles.pinyin.ass",
            alternating_subtitle_path=work_dir / "subtitles.alternating.ass",
            mode1_path=output_dir / f"{slug}.mode1-nosubs.mp4",
            mode2_path=output_dir / f"{slug}.mode2-pinyin.mp4",
            mode3_path=output_dir / f"{slug}.mode3-alternating.mp4",
        )

    def ensure_directories(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


def scan_input_videos(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    return sorted(
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
    )
```

- [ ] **Step 5: Implement manifest state**

Create `src/chinese_media_feeder/manifest.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ManifestStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"episodes": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def update_step(
        self,
        slug: str,
        input_path: Path,
        step: str,
        status: str,
        artifacts: dict[str, Path] | None = None,
        outputs: dict[str, Path] | None = None,
        models: dict[str, str] | None = None,
        error: str | None = None,
    ) -> None:
        data = self.load()
        episode = data["episodes"].setdefault(slug, {})
        episode["input_path"] = str(input_path)
        episode.setdefault("steps", {})
        episode.setdefault("artifacts", {})
        episode.setdefault("outputs", {})
        episode.setdefault("models", {})
        episode["steps"][step] = {
            "status": status,
            "updated_at": _now_iso(),
        }
        if error:
            episode["steps"][step]["error"] = error
        for key, value in (artifacts or {}).items():
            episode["artifacts"][key] = str(value)
        for key, value in (outputs or {}).items():
            episode["outputs"][key] = str(value)
        for key, value in (models or {}).items():
            episode["models"][key] = value
        episode["updated_at"] = _now_iso()
        self.save(data)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
```

- [ ] **Step 6: Run the episode and manifest tests to verify they pass**

Run: `pytest tests/test_episodes.py tests/test_manifest.py -v`

Expected: PASS with `5 passed`.

- [ ] **Step 7: Commit episode and manifest support**

```bash
git add src/chinese_media_feeder/episodes.py src/chinese_media_feeder/manifest.py tests/test_episodes.py tests/test_manifest.py
git commit -m "feat: add episode paths and manifest state"
```

---

### Task 3: Cue Model and Transcript Normalization

**Files:**
- Create: `src/chinese_media_feeder/cues.py`
- Create: `tests/fixtures/transcript.diarized.json`
- Test: `tests/test_cues.py`

- [ ] **Step 1: Create the transcript fixture**

Create `tests/fixtures/transcript.diarized.json`:

```json
{
  "segments": [
    {
      "start": 0.4,
      "end": 2.1,
      "text": "你好，佩奇。",
      "speaker": "SPEAKER_00"
    },
    {
      "start": 2.2,
      "end": 3.8,
      "text": "你好，乔治！",
      "speaker": "SPEAKER_01"
    }
  ]
}
```

- [ ] **Step 2: Write failing cue normalization tests**

Create `tests/test_cues.py`:

```python
import json

from chinese_media_feeder.cues import Cue, cue_from_dict, cue_to_dict, normalize_transcript


def test_normalize_transcript_reads_segments_fixture():
    raw = json.loads(open("tests/fixtures/transcript.diarized.json", encoding="utf-8").read())

    cues = normalize_transcript(raw)

    assert cues == [
        Cue(index=1, start=0.4, end=2.1, speaker="SPEAKER_00", chinese="你好，佩奇。"),
        Cue(index=2, start=2.2, end=3.8, speaker="SPEAKER_01", chinese="你好，乔治！"),
    ]


def test_cue_round_trip_preserves_optional_learning_fields():
    cue = Cue(
        index=1,
        start=0.0,
        end=1.25,
        speaker="SPEAKER_00",
        chinese="我来了。",
        pinyin="wo lai le.",
        english="I'm coming.",
    )

    assert cue_from_dict(cue_to_dict(cue)) == cue
```

- [ ] **Step 3: Run the cue tests to verify they fail**

Run: `pytest tests/test_cues.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'chinese_media_feeder.cues'`.

- [ ] **Step 4: Implement cue normalization**

Create `src/chinese_media_feeder/cues.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Cue:
    index: int
    start: float
    end: float
    speaker: str | None
    chinese: str
    pinyin: str | None = None
    english: str | None = None


def normalize_transcript(raw: dict[str, Any]) -> list[Cue]:
    segments = raw.get("segments") or raw.get("diarized_segments") or []
    cues: list[Cue] = []
    for offset, segment in enumerate(segments, start=1):
        text = str(segment.get("text") or segment.get("transcript") or "").strip()
        if not text:
            continue
        cues.append(
            Cue(
                index=len(cues) + 1,
                start=float(segment["start"]),
                end=float(segment["end"]),
                speaker=segment.get("speaker") or segment.get("speaker_label"),
                chinese=text,
            )
        )
    return cues


def cue_to_dict(cue: Cue) -> dict[str, Any]:
    return {
        "index": cue.index,
        "start": cue.start,
        "end": cue.end,
        "speaker": cue.speaker,
        "chinese": cue.chinese,
        "pinyin": cue.pinyin,
        "english": cue.english,
    }


def cue_from_dict(data: dict[str, Any]) -> Cue:
    return Cue(
        index=int(data["index"]),
        start=float(data["start"]),
        end=float(data["end"]),
        speaker=data.get("speaker"),
        chinese=str(data["chinese"]),
        pinyin=data.get("pinyin"),
        english=data.get("english"),
    )
```

- [ ] **Step 5: Run the cue tests to verify they pass**

Run: `pytest tests/test_cues.py -v`

Expected: PASS with `2 passed`.

- [ ] **Step 6: Commit cue normalization**

```bash
git add src/chinese_media_feeder/cues.py tests/fixtures/transcript.diarized.json tests/test_cues.py
git commit -m "feat: normalize transcript cues"
```

---

### Task 4: Pinyin Conversion and ASS Subtitle Generation

**Files:**
- Create: `src/chinese_media_feeder/pinyin.py`
- Create: `src/chinese_media_feeder/subtitles.py`
- Test: `tests/test_pinyin.py`
- Test: `tests/test_subtitles.py`

- [ ] **Step 1: Write failing pinyin tests**

Create `tests/test_pinyin.py`:

```python
from chinese_media_feeder.pinyin import chinese_to_pinyin


def test_chinese_to_pinyin_uses_tone_marks():
    assert chinese_to_pinyin("你好，佩奇。") == "nǐ hǎo, pèi qí."
```

- [ ] **Step 2: Write failing subtitle tests**

Create `tests/test_subtitles.py`:

```python
from chinese_media_feeder.cues import Cue
from chinese_media_feeder.subtitles import ass_time, build_alternating_events, escape_ass_text, render_ass


def test_ass_time_formats_hundredths():
    assert ass_time(65.43) == "0:01:05.43"


def test_escape_ass_text_handles_special_characters_and_newlines():
    assert escape_ass_text("a{b}\nc") == "a\\{b\\}\\Nc"


def test_build_alternating_events_switches_between_pinyin_and_english():
    cues = [
        Cue(index=1, start=0, end=1, speaker="A", chinese="你好", pinyin="ni hao", english="Hello"),
        Cue(index=2, start=1, end=2, speaker="B", chinese="再见", pinyin="zai jian", english="Bye"),
        Cue(index=3, start=2, end=3, speaker="A", chinese="来了", pinyin="lai le", english="Coming"),
    ]

    events = build_alternating_events(cues)

    assert [event.text for event in events] == ["ni hao", "Bye", "lai le"]


def test_render_ass_contains_dialogue_lines():
    cues = [
        Cue(index=1, start=0, end=1.5, speaker=None, chinese="你好", pinyin="ni hao", english="Hello"),
    ]

    content = render_ass(cues, mode="pinyin")

    assert "[Script Info]" in content
    assert "Style: Default" in content
    assert "Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,ni hao" in content
```

- [ ] **Step 3: Run pinyin and subtitle tests to verify they fail**

Run: `pytest tests/test_pinyin.py tests/test_subtitles.py -v`

Expected: FAIL with import errors for `chinese_media_feeder.pinyin` and `chinese_media_feeder.subtitles`.

- [ ] **Step 4: Implement pinyin conversion**

Create `src/chinese_media_feeder/pinyin.py`:

```python
from __future__ import annotations

from pypinyin import Style, pinyin


PUNCTUATION_MAP = {
    "，": ",",
    "。": ".",
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
}


def chinese_to_pinyin(text: str) -> str:
    syllables: list[str] = []
    for item in pinyin(text, style=Style.TONE, neutral_tone_with_five=False, errors=_handle_non_chinese):
        syllables.append(item[0])
    return _clean_spacing(" ".join(syllables))


def _handle_non_chinese(chars: str) -> list[str]:
    return [PUNCTUATION_MAP.get(char, char) for char in chars]


def _clean_spacing(text: str) -> str:
    for mark in [",", ".", "!", "?", ":", ";"]:
        text = text.replace(f" {mark}", mark)
    return " ".join(text.split())
```

- [ ] **Step 5: Implement ASS subtitle generation**

Create `src/chinese_media_feeder/subtitles.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chinese_media_feeder.cues import Cue


@dataclass(frozen=True)
class SubtitleEvent:
    start: float
    end: float
    text: str


def ass_time(seconds: float) -> str:
    total_hundredths = int(round(seconds * 100))
    hundredths = total_hundredths % 100
    total_seconds = total_hundredths // 100
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours}:{mins:02d}:{secs:02d}.{hundredths:02d}"


def escape_ass_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def build_pinyin_events(cues: list[Cue]) -> list[SubtitleEvent]:
    return [SubtitleEvent(cue.start, cue.end, cue.pinyin or "") for cue in cues]


def build_alternating_events(cues: list[Cue]) -> list[SubtitleEvent]:
    events: list[SubtitleEvent] = []
    for zero_index, cue in enumerate(cues):
        text = cue.pinyin if zero_index % 2 == 0 else cue.english
        events.append(SubtitleEvent(cue.start, cue.end, text or ""))
    return events


def render_ass(cues: list[Cue], mode: str) -> str:
    if mode == "pinyin":
        events = build_pinyin_events(cues)
    elif mode == "alternating":
        events = build_alternating_events(cues)
    else:
        raise ValueError(f"Unsupported subtitle mode: {mode}")

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1280",
        "PlayResY: 720",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,54,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for event in events:
        lines.append(
            f"Dialogue: 0,{ass_time(event.start)},{ass_time(event.end)},Default,,0,0,0,,{escape_ass_text(event.text)}"
        )
    return "\n".join(lines) + "\n"


def write_ass(path: Path, cues: list[Cue], mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ass(cues, mode=mode), encoding="utf-8")
```

- [ ] **Step 6: Run pinyin and subtitle tests to verify they pass**

Run: `pytest tests/test_pinyin.py tests/test_subtitles.py -v`

Expected: PASS with `5 passed`.

- [ ] **Step 7: Commit pinyin and subtitle support**

```bash
git add src/chinese_media_feeder/pinyin.py src/chinese_media_feeder/subtitles.py tests/test_pinyin.py tests/test_subtitles.py
git commit -m "feat: add pinyin and subtitle generation"
```

---

### Task 5: ffmpeg Media Operations

**Files:**
- Create: `src/chinese_media_feeder/media.py`
- Test: `tests/test_media.py`

- [ ] **Step 1: Write failing media command tests**

Create `tests/test_media.py`:

```python
from pathlib import Path

from chinese_media_feeder.media import build_burn_subtitles_command, build_extract_audio_command, build_mode1_command


def test_build_extract_audio_command_compresses_to_m4a():
    command = build_extract_audio_command(Path("in.mp4"), Path("audio.m4a"), bitrate="48k")

    assert command == [
        "ffmpeg", "-y", "-i", "in.mp4", "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", "audio.m4a"
    ]


def test_build_mode1_command_normalizes_to_h264_mp4():
    command = build_mode1_command(Path("in.mkv"), Path("out.mp4"))

    assert command == [
        "ffmpeg", "-y", "-i", "in.mkv", "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", "out.mp4"
    ]


def test_build_burn_subtitles_command_uses_ass_filter():
    command = build_burn_subtitles_command(Path("in.mp4"), Path("subs.ass"), Path("out.mp4"))

    assert command == [
        "ffmpeg", "-y", "-i", "in.mp4", "-vf", "ass=subs.ass", "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", "out.mp4"
    ]
```

- [ ] **Step 2: Run media tests to verify they fail**

Run: `pytest tests/test_media.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'chinese_media_feeder.media'`.

- [ ] **Step 3: Implement ffmpeg command construction and runner**

Create `src/chinese_media_feeder/media.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


def build_extract_audio_command(input_path: Path, output_path: Path, bitrate: str = "48k") -> list[str]:
    return [
        "ffmpeg", "-y", "-i", str(input_path), "-vn", "-ac", "1", "-ar", "16000", "-b:a", bitrate, str(output_path)
    ]


def build_mode1_command(input_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg", "-y", "-i", str(input_path), "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(output_path)
    ]


def build_burn_subtitles_command(input_path: Path, subtitle_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        f"ass={subtitle_path}",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


class MediaRunner:
    def run(self, command: list[str]) -> None:
        subprocess.run(command, check=True)

    def extract_audio(self, input_path: Path, output_path: Path, bitrate: str = "48k") -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.run(build_extract_audio_command(input_path, output_path, bitrate=bitrate))

    def render_mode1(self, input_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.run(build_mode1_command(input_path, output_path))

    def burn_subtitles(self, input_path: Path, subtitle_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.run(build_burn_subtitles_command(input_path, subtitle_path, output_path))
```

- [ ] **Step 4: Run media tests to verify they pass**

Run: `pytest tests/test_media.py -v`

Expected: PASS with `3 passed`.

- [ ] **Step 5: Commit media operations**

```bash
git add src/chinese_media_feeder/media.py tests/test_media.py
git commit -m "feat: add ffmpeg media operations"
```

---

### Task 6: OpenAI Adapter

**Files:**
- Create: `src/chinese_media_feeder/openai_client.py`
- Test: extend `tests/test_cues.py` only if the adapter needs fixture mapping tests; otherwise keep API calls untested at unit level.

- [ ] **Step 1: Implement the OpenAI adapter with explicit methods**

Create `src/chinese_media_feeder/openai_client.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from openai import OpenAI

from chinese_media_feeder.cues import Cue


class OpenAIAdapter:
    def __init__(self, api_key: str, transcribe_model: str, translation_model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.transcribe_model = transcribe_model
        self.translation_model = translation_model

    def transcribe(self, audio_path: Path) -> dict:
        with audio_path.open("rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model=self.transcribe_model,
                file=audio_file,
                response_format="diarized_json",
            )
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if isinstance(response, dict):
            return response
        return json.loads(response)

    def translate_cues(self, cues: list[Cue]) -> dict[int, str]:
        payload = [{"index": cue.index, "chinese": cue.chinese} for cue in cues]
        response = self.client.responses.create(
            model=self.translation_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Translate Mandarin subtitle cues into short, natural, child-friendly English. "
                        "Preserve the input indexes exactly. Return only JSON with a translations array."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"cues": payload}, ensure_ascii=False),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "cue_translations",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["translations"],
                        "properties": {
                            "translations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["index", "english"],
                                    "properties": {
                                        "index": {"type": "integer"},
                                        "english": {"type": "string"},
                                    },
                                },
                            }
                        },
                    },
                    "strict": True,
                }
            },
        )
        data = json.loads(response.output_text)
        return {int(item["index"]): str(item["english"]) for item in data["translations"]}
```

- [ ] **Step 2: Run import checks**

Run: `python -c "from chinese_media_feeder.openai_client import OpenAIAdapter; print(OpenAIAdapter.__name__)"`

Expected: prints `OpenAIAdapter`.

- [ ] **Step 3: Commit OpenAI adapter**

```bash
git add src/chinese_media_feeder/openai_client.py
git commit -m "feat: add OpenAI media adapter"
```

---

### Task 7: Pipeline Orchestration With Fakes

**Files:**
- Create: `src/chinese_media_feeder/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing pipeline test**

Create `tests/test_pipeline.py`:

```python
from pathlib import Path

from chinese_media_feeder.config import Settings
from chinese_media_feeder.pipeline import EpisodeProcessor


class FakeOpenAI:
    def transcribe(self, audio_path: Path) -> dict:
        return {
            "segments": [
                {"start": 0.0, "end": 1.0, "speaker": "A", "text": "你好"},
                {"start": 1.0, "end": 2.0, "speaker": "B", "text": "再见"},
            ]
        }

    def translate_cues(self, cues):
        return {1: "Hello", 2: "Bye"}


class FakeMediaRunner:
    def __init__(self):
        self.calls = []

    def extract_audio(self, input_path: Path, output_path: Path, bitrate: str = "48k") -> None:
        self.calls.append(("extract_audio", input_path, output_path, bitrate))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("audio")

    def render_mode1(self, input_path: Path, output_path: Path) -> None:
        self.calls.append(("render_mode1", input_path, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("mode1")

    def burn_subtitles(self, input_path: Path, subtitle_path: Path, output_path: Path) -> None:
        self.calls.append(("burn_subtitles", input_path, subtitle_path, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("rendered")


def test_episode_processor_writes_artifacts_and_outputs(tmp_path):
    input_path = tmp_path / "input" / "peppa-001.mp4"
    input_path.parent.mkdir()
    input_path.write_text("video")
    settings = Settings(
        openai_api_key="sk-test",
        transcribe_model="gpt-4o-transcribe-diarize",
        translation_model="gpt-5.4-mini",
        input_dir=tmp_path / "input",
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "output",
        manifest_path=tmp_path / "manifest.json",
    )
    media = FakeMediaRunner()
    processor = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=media)

    paths = processor.process(input_path)

    assert paths.raw_transcript_path.exists()
    assert paths.normalized_cues_path.exists()
    assert paths.pinyin_subtitle_path.exists()
    assert paths.alternating_subtitle_path.exists()
    assert paths.mode1_path.read_text() == "mode1"
    assert paths.mode2_path.read_text() == "rendered"
    assert paths.mode3_path.read_text() == "rendered"
```

- [ ] **Step 2: Run pipeline test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'chinese_media_feeder.pipeline'`.

- [ ] **Step 3: Implement the processor**

Create `src/chinese_media_feeder/pipeline.py`:

```python
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from chinese_media_feeder.config import Settings
from chinese_media_feeder.cues import Cue, cue_to_dict, normalize_transcript
from chinese_media_feeder.episodes import EpisodePaths
from chinese_media_feeder.manifest import ManifestStore
from chinese_media_feeder.media import MediaRunner
from chinese_media_feeder.pinyin import chinese_to_pinyin
from chinese_media_feeder.subtitles import write_ass


class TranscriberTranslator(Protocol):
    def transcribe(self, audio_path: Path) -> dict:
        raise NotImplementedError

    def translate_cues(self, cues: list[Cue]) -> dict[int, str]:
        raise NotImplementedError


class EpisodeProcessor:
    def __init__(self, settings: Settings, openai: TranscriberTranslator, media: MediaRunner | None = None) -> None:
        self.settings = settings
        self.openai = openai
        self.media = media or MediaRunner()
        self.manifest = ManifestStore(settings.manifest_path)

    def process(self, input_path: Path, force: bool = False) -> EpisodePaths:
        paths = EpisodePaths.from_input(input_path, self.settings.work_dir, self.settings.output_dir)
        paths.ensure_directories()

        if force or not paths.mode1_path.exists():
            self.media.render_mode1(paths.input_path, paths.mode1_path)
            self.manifest.update_step(
                paths.slug,
                paths.input_path,
                "render_mode1",
                "complete",
                outputs={"mode1": paths.mode1_path},
            )

        if force or not paths.audio_path.exists():
            self.media.extract_audio(paths.input_path, paths.audio_path)
            self.manifest.update_step(
                paths.slug,
                paths.input_path,
                "extract_audio",
                "complete",
                artifacts={"audio": paths.audio_path},
            )

        if force or not paths.raw_transcript_path.exists():
            raw_transcript = self.openai.transcribe(paths.audio_path)
            paths.raw_transcript_path.write_text(
                json.dumps(raw_transcript, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.manifest.update_step(
                paths.slug,
                paths.input_path,
                "transcribe",
                "complete",
                artifacts={"raw_transcript": paths.raw_transcript_path},
                models={"transcribe": self.settings.transcribe_model},
            )
        else:
            raw_transcript = json.loads(paths.raw_transcript_path.read_text(encoding="utf-8"))

        cues = normalize_transcript(raw_transcript)
        cues = [replace(cue, pinyin=chinese_to_pinyin(cue.chinese)) for cue in cues]
        translations = self.openai.translate_cues(cues)
        cues = [replace(cue, english=translations.get(cue.index, "")) for cue in cues]

        paths.normalized_cues_path.write_text(
            json.dumps([cue_to_dict(cue) for cue in cues], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.manifest.update_step(
            paths.slug,
            paths.input_path,
            "build_cues",
            "complete",
            artifacts={"normalized_cues": paths.normalized_cues_path},
            models={"translation": self.settings.translation_model},
        )

        write_ass(paths.pinyin_subtitle_path, cues, mode="pinyin")
        write_ass(paths.alternating_subtitle_path, cues, mode="alternating")
        self.manifest.update_step(
            paths.slug,
            paths.input_path,
            "write_subtitles",
            "complete",
            artifacts={
                "pinyin_subtitles": paths.pinyin_subtitle_path,
                "alternating_subtitles": paths.alternating_subtitle_path,
            },
        )

        if force or not paths.mode2_path.exists():
            self.media.burn_subtitles(paths.input_path, paths.pinyin_subtitle_path, paths.mode2_path)
            self.manifest.update_step(
                paths.slug,
                paths.input_path,
                "render_mode2",
                "complete",
                outputs={"mode2": paths.mode2_path},
            )

        if force or not paths.mode3_path.exists():
            self.media.burn_subtitles(paths.input_path, paths.alternating_subtitle_path, paths.mode3_path)
            self.manifest.update_step(
                paths.slug,
                paths.input_path,
                "render_mode3",
                "complete",
                outputs={"mode3": paths.mode3_path},
            )

        return paths
```

- [ ] **Step 4: Run pipeline test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`

Expected: PASS with `1 passed`.

- [ ] **Step 5: Commit pipeline orchestration**

```bash
git add src/chinese_media_feeder/pipeline.py tests/test_pipeline.py
git commit -m "feat: add media generation pipeline"
```

---

### Task 8: CLI Commands

**Files:**
- Create: `src/chinese_media_feeder/cli.py`

- [ ] **Step 1: Implement the CLI**

Create `src/chinese_media_feeder/cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import typer

from chinese_media_feeder.config import Settings
from chinese_media_feeder.episodes import EpisodePaths, scan_input_videos
from chinese_media_feeder.manifest import ManifestStore
from chinese_media_feeder.openai_client import OpenAIAdapter
from chinese_media_feeder.pipeline import EpisodeProcessor

app = typer.Typer(help="Generate Mandarin learner video variants.")


@app.command()
def scan() -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    videos = scan_input_videos(settings.input_dir)
    for video in videos:
        paths = EpisodePaths.from_input(video, settings.work_dir, settings.output_dir)
        typer.echo(f"{paths.slug}\t{video}")
    if not videos:
        typer.echo(f"No supported videos found in {settings.input_dir}")


@app.command("process")
def process_file(input_file: Path, force: bool = False) -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    if settings.openai_api_key is None:
        raise typer.BadParameter("OPENAI_API_KEY is required for processing.")
    adapter = OpenAIAdapter(
        api_key=settings.openai_api_key,
        transcribe_model=settings.transcribe_model,
        translation_model=settings.translation_model,
    )
    processor = EpisodeProcessor(settings=settings, openai=adapter)
    paths = processor.process(input_file, force=force)
    typer.echo(f"Generated {paths.output_dir}")


@app.command("process-all")
def process_all(force: bool = False) -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    if settings.openai_api_key is None:
        raise typer.BadParameter("OPENAI_API_KEY is required for processing.")
    adapter = OpenAIAdapter(
        api_key=settings.openai_api_key,
        transcribe_model=settings.transcribe_model,
        translation_model=settings.translation_model,
    )
    processor = EpisodeProcessor(settings=settings, openai=adapter)
    for video in scan_input_videos(settings.input_dir):
        paths = processor.process(video, force=force)
        typer.echo(f"Generated {paths.output_dir}")


@app.command()
def status() -> None:
    settings = Settings.from_env()
    data = ManifestStore(settings.manifest_path).load()
    episodes = data["episodes"]
    if not episodes:
        typer.echo("No episodes processed.")
        return
    for slug, episode in sorted(episodes.items()):
        steps = episode.get("steps", {})
        completed = [name for name, info in steps.items() if info.get("status") == "complete"]
        typer.echo(f"{slug}\t{', '.join(completed)}")
```

- [ ] **Step 2: Run CLI import check**

Run: `python -c "from chinese_media_feeder.cli import app; print(app.info.help)"`

Expected: prints `Generate Mandarin learner video variants.`

- [ ] **Step 3: Run full unit suite**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 4: Commit CLI commands**

```bash
git add src/chinese_media_feeder/cli.py
git commit -m "feat: add media generator CLI"
```

---

### Task 9: Docker Packaging and Final Verification

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `media/input/.gitkeep`
- Create: `media/work/.gitkeep`
- Create: `media/output/.gitkeep`

- [ ] **Step 1: Add Docker files**

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

CMD ["cmf", "status"]
```

Create `docker-compose.yml`:

```yaml
services:
  cmf:
    build: .
    env_file:
      - .env
    volumes:
      - ./media:/app/media
    command: ["cmf", "status"]
```

Create empty files:

```text
media/input/.gitkeep
media/work/.gitkeep
media/output/.gitkeep
```

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 3: Build Docker image**

Run: `docker compose build`

Expected: build completes successfully and installs `chinese-media-feeder`.

- [ ] **Step 4: Run Docker status command**

Run: `docker compose run --rm cmf cmf status`

Expected: prints `No episodes processed.`

- [ ] **Step 5: Commit Docker packaging**

```bash
git add Dockerfile docker-compose.yml media/input/.gitkeep media/work/.gitkeep media/output/.gitkeep
git commit -m "chore: add docker packaging"
```

---

## Plan Self-Review

- Spec coverage: local file input, three MP4 outputs, OpenAI transcription and translation, pypinyin conversion, ffmpeg rendering, JSON manifest, resumable artifacts, CLI commands, and Docker-friendly VPS packaging are all covered by tasks above.
- Explicitly out of scope: Telegram bot, YouTube playlist ingestion, web UI, transcript editor, and local speech models are not implemented in this plan.
- Type consistency: `Settings`, `EpisodePaths`, `Cue`, `ManifestStore`, `MediaRunner`, `OpenAIAdapter`, and `EpisodeProcessor` names are defined before use in later tasks.
- Paid API containment: tests use fixtures and fakes; only `cmf process` and `cmf process-all` call OpenAI.
