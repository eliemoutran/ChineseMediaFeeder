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
    def from_env(cls, load_dotenv_file: bool = True) -> "Settings":
        if load_dotenv_file:
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
