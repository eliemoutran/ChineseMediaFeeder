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
