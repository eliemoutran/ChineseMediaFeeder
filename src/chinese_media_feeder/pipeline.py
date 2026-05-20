from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from chinese_media_feeder.config import Settings
from chinese_media_feeder.cues import Cue, cue_from_dict, cue_to_dict, normalize_transcript
from chinese_media_feeder.episodes import EpisodePaths
from chinese_media_feeder.manifest import ManifestStore
from chinese_media_feeder.media import MediaRunner
from chinese_media_feeder.pinyin import chinese_to_pinyin
from chinese_media_feeder.subtitles import write_ass


class TranscriberTranslator(Protocol):
    def transcribe(self, audio_path: Path) -> dict:
        ...

    def translate_cues(self, cues: list[Cue]) -> dict[int, str]:
        ...


@dataclass(frozen=True)
class CueBuildResult:
    cues: list[Cue]
    pinyin_subtitles_changed: bool = False
    alternating_subtitles_changed: bool = False


class EpisodeProcessor:
    def __init__(self, settings: Settings, openai: TranscriberTranslator, media: MediaRunner | None = None) -> None:
        self.settings = settings
        self.openai = openai
        self.media = media or MediaRunner()
        self.manifest = ManifestStore(settings.manifest_path)

    def process_paths(self, input_path: Path) -> EpisodePaths:
        return EpisodePaths.from_input(input_path, self.settings.work_dir, self.settings.output_dir)

    def process(self, input_path: Path, force: bool = False) -> EpisodePaths:
        paths = self.process_paths(input_path)
        paths.ensure_directories()

        if force or not paths.mode1_path.exists():
            try:
                self.media.render_mode1(paths.input_path, paths.mode1_path)
                self.manifest.update_step(
                    paths.slug,
                    paths.input_path,
                    "render_mode1",
                    "complete",
                    outputs={"mode1": paths.mode1_path},
                )
            except Exception as exc:
                _delete_if_exists(paths.mode1_path)
                self._record_failure(paths, "render_mode1", exc, outputs={"mode1": paths.mode1_path})
                raise

        if force or not paths.audio_path.exists():
            try:
                self.media.extract_audio(paths.input_path, paths.audio_path)
                self.manifest.update_step(
                    paths.slug,
                    paths.input_path,
                    "extract_audio",
                    "complete",
                    artifacts={"audio": paths.audio_path},
                )
            except Exception as exc:
                _delete_if_exists(paths.audio_path)
                self._record_failure(paths, "extract_audio", exc, artifacts={"audio": paths.audio_path})
                raise

        if force or not paths.raw_transcript_path.exists():
            try:
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
            except Exception as exc:
                self._record_failure(
                    paths,
                    "transcribe",
                    exc,
                    artifacts={"raw_transcript": paths.raw_transcript_path},
                    models={"transcribe": self.settings.transcribe_model},
                )
                raise

        cue_result = self._build_cues(paths, force=force)
        cues = cue_result.cues
        pinyin_subtitles_changed = cue_result.pinyin_subtitles_changed
        alternating_subtitles_changed = cue_result.alternating_subtitles_changed

        if force or not paths.pinyin_subtitle_path.exists() or not paths.alternating_subtitle_path.exists():
            try:
                if force or not paths.pinyin_subtitle_path.exists():
                    _invalidate_pinyin_subtitle(paths)
                    _write_subtitle_atomically(paths.pinyin_subtitle_path, cues, mode="pinyin")
                    pinyin_subtitles_changed = True
                if force or not paths.alternating_subtitle_path.exists():
                    _invalidate_alternating_subtitle(paths)
                    _write_subtitle_atomically(paths.alternating_subtitle_path, cues, mode="alternating")
                    alternating_subtitles_changed = True
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
            except Exception as exc:
                self._record_failure(
                    paths,
                    "write_subtitles",
                    exc,
                    artifacts={
                        "pinyin_subtitles": paths.pinyin_subtitle_path,
                        "alternating_subtitles": paths.alternating_subtitle_path,
                    },
                )
                raise

        if force or pinyin_subtitles_changed or not paths.mode2_path.exists():
            try:
                self.media.burn_subtitles(paths.input_path, paths.pinyin_subtitle_path, paths.mode2_path)
                self.manifest.update_step(
                    paths.slug,
                    paths.input_path,
                    "render_mode2",
                    "complete",
                    outputs={"mode2": paths.mode2_path},
                )
            except Exception as exc:
                _delete_if_exists(paths.mode2_path)
                self._record_failure(paths, "render_mode2", exc, outputs={"mode2": paths.mode2_path})
                raise

        if force or alternating_subtitles_changed or not paths.mode3_path.exists():
            try:
                self.media.burn_subtitles(paths.input_path, paths.alternating_subtitle_path, paths.mode3_path)
                self.manifest.update_step(
                    paths.slug,
                    paths.input_path,
                    "render_mode3",
                    "complete",
                    outputs={"mode3": paths.mode3_path},
                )
            except Exception as exc:
                _delete_if_exists(paths.mode3_path)
                self._record_failure(paths, "render_mode3", exc, outputs={"mode3": paths.mode3_path})
                raise

        return paths

    def _build_cues(self, paths: EpisodePaths, force: bool) -> CueBuildResult:
        try:
            pinyin_changed = False
            pinyin_subtitles_changed = False
            alternating_subtitles_changed = False
            if not force and paths.normalized_cues_path.exists():
                cues = _read_cues(paths.normalized_cues_path)
                cues, pinyin_changed = _enrich_missing_pinyin(cues)
                if pinyin_changed:
                    _write_cues(paths.normalized_cues_path, cues)
                if _has_complete_cues(cues):
                    if pinyin_changed or not paths.pinyin_subtitle_path.exists():
                        _invalidate_pinyin_subtitle(paths)
                        _write_subtitle_atomically(paths.pinyin_subtitle_path, cues, mode="pinyin")
                        pinyin_subtitles_changed = True
                    if pinyin_changed and paths.alternating_subtitle_path.exists():
                        _invalidate_alternating_subtitle(paths)
                        _write_subtitle_atomically(paths.alternating_subtitle_path, cues, mode="alternating")
                        alternating_subtitles_changed = True
                    return CueBuildResult(
                        cues,
                        pinyin_subtitles_changed=pinyin_subtitles_changed,
                        alternating_subtitles_changed=alternating_subtitles_changed,
                    )
            else:
                raw_transcript = json.loads(paths.raw_transcript_path.read_text(encoding="utf-8"))
                cues = normalize_transcript(raw_transcript)
                cues = [replace(cue, pinyin=chinese_to_pinyin(cue.chinese)) for cue in cues]
                _write_cues(paths.normalized_cues_path, cues)
                pinyin_changed = True

            if force or pinyin_changed or not paths.pinyin_subtitle_path.exists():
                _invalidate_pinyin_subtitle(paths)
                _write_subtitle_atomically(paths.pinyin_subtitle_path, cues, mode="pinyin")
                pinyin_subtitles_changed = True

            translations = self.openai.translate_cues(cues)
            _validate_translation_indexes(cues, translations)
            cues = [replace(cue, english=translations[cue.index]) for cue in cues]
            _write_cues(paths.normalized_cues_path, cues)
            if paths.alternating_subtitle_path.exists():
                _invalidate_alternating_subtitle(paths)
                _write_subtitle_atomically(paths.alternating_subtitle_path, cues, mode="alternating")
                alternating_subtitles_changed = True
            self.manifest.update_step(
                paths.slug,
                paths.input_path,
                "build_cues",
                "complete",
                artifacts={"normalized_cues": paths.normalized_cues_path},
                models={"translation": self.settings.translation_model},
            )
            return CueBuildResult(
                cues,
                pinyin_subtitles_changed=pinyin_subtitles_changed,
                alternating_subtitles_changed=alternating_subtitles_changed,
            )
        except Exception as exc:
            self._record_failure(
                paths,
                "build_cues",
                exc,
                artifacts={
                    "normalized_cues": paths.normalized_cues_path,
                    "pinyin_subtitles": paths.pinyin_subtitle_path,
                },
                models={"translation": self.settings.translation_model},
            )
            raise

    def _record_failure(
        self,
        paths: EpisodePaths,
        step: str,
        exc: Exception,
        artifacts: dict[str, Path] | None = None,
        outputs: dict[str, Path] | None = None,
        models: dict[str, str] | None = None,
    ) -> None:
        self.manifest.update_step(
            paths.slug,
            paths.input_path,
            step,
            "failed",
            artifacts=artifacts,
            outputs=outputs,
            models=models,
            error=str(exc),
        )


def _read_cues(path: Path) -> list[Cue]:
    return [cue_from_dict(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def _write_cues(path: Path, cues: list[Cue]) -> None:
    path.write_text(
        json.dumps([cue_to_dict(cue) for cue in cues], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_subtitle_atomically(path: Path, cues: list[Cue], mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        write_ass(temp_path, cues, mode=mode)
        temp_path.replace(path)
    except Exception:
        _delete_if_exists(temp_path)
        raise


def _invalidate_pinyin_subtitle(paths: EpisodePaths) -> None:
    _delete_if_exists(paths.pinyin_subtitle_path)
    _delete_if_exists(paths.mode2_path)


def _invalidate_alternating_subtitle(paths: EpisodePaths) -> None:
    _delete_if_exists(paths.alternating_subtitle_path)
    _delete_if_exists(paths.mode3_path)


def _delete_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _has_complete_cues(cues: list[Cue]) -> bool:
    return all(_has_text(cue.pinyin) and _has_text(cue.english) for cue in cues)


def _enrich_missing_pinyin(cues: list[Cue]) -> tuple[list[Cue], bool]:
    changed = False
    enriched = []
    for cue in cues:
        if _has_text(cue.pinyin):
            enriched.append(cue)
            continue
        enriched.append(replace(cue, pinyin=chinese_to_pinyin(cue.chinese)))
        changed = True
    return enriched, changed


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _validate_translation_indexes(cues: list[Cue], translations: dict[int, str]) -> None:
    expected = {cue.index for cue in cues}
    actual = set(translations)
    if actual != expected:
        raise ValueError(
            "Translation indexes do not match cue indexes: "
            f"expected {sorted(expected)}, got {sorted(actual)}"
        )
