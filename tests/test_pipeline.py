import json
from pathlib import Path

import pytest

import chinese_media_feeder.pipeline as pipeline_module
from chinese_media_feeder.config import Settings
from chinese_media_feeder.pipeline import EpisodeProcessor
from chinese_media_feeder.subtitles import write_ass as real_write_ass


class FakeOpenAI:
    def __init__(self, translations=None):
        self.transcribe_calls = 0
        self.translate_calls = 0
        self.translations = translations or {1: "Hello", 2: "Bye"}

    def transcribe(self, audio_path: Path) -> dict:
        self.transcribe_calls += 1
        return {
            "segments": [
                {"start": 0.0, "end": 1.0, "speaker": "A", "text": "你好"},
                {"start": 1.0, "end": 2.0, "speaker": "B", "text": "再见"},
            ]
        }

    def translate_cues(self, cues):
        self.translate_calls += 1
        return self.translations


class FailingOpenAI(FakeOpenAI):
    def transcribe(self, audio_path: Path) -> dict:
        raise AssertionError("transcribe should not be called")

    def translate_cues(self, cues):
        raise AssertionError("translate_cues should not be called")


class TranslationErrorOpenAI(FakeOpenAI):
    def translate_cues(self, cues):
        self.translate_calls += 1
        raise RuntimeError("translation unavailable")


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


class FailingRenderMediaRunner(FakeMediaRunner):
    def burn_subtitles(self, input_path: Path, subtitle_path: Path, output_path: Path) -> None:
        self.calls.append(("burn_subtitles", input_path, subtitle_path, output_path))
        raise RuntimeError("render failed")


class PartialMode1MediaRunner(FakeMediaRunner):
    def render_mode1(self, input_path: Path, output_path: Path) -> None:
        self.calls.append(("render_mode1", input_path, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("partial mode1")
        raise RuntimeError("mode1 failed")


class PartialAudioMediaRunner(FakeMediaRunner):
    def extract_audio(self, input_path: Path, output_path: Path, bitrate: str = "48k") -> None:
        self.calls.append(("extract_audio", input_path, output_path, bitrate))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("partial audio")
        raise RuntimeError("audio failed")


class PartialMode2MediaRunner(FakeMediaRunner):
    def burn_subtitles(self, input_path: Path, subtitle_path: Path, output_path: Path) -> None:
        self.calls.append(("burn_subtitles", input_path, subtitle_path, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("partial mode2")
        if "mode2" in output_path.name:
            raise RuntimeError("mode2 failed")


class PartialMode3MediaRunner(FakeMediaRunner):
    def burn_subtitles(self, input_path: Path, subtitle_path: Path, output_path: Path) -> None:
        self.calls.append(("burn_subtitles", input_path, subtitle_path, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("partial mode3")
        if "mode3" in output_path.name:
            raise RuntimeError("mode3 failed")


def make_settings(tmp_path):
    return Settings(
        openai_api_key="sk-test",
        transcribe_model="gpt-4o-transcribe-diarize",
        translation_model="gpt-5.4-mini",
        input_dir=tmp_path / "input",
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "output",
        manifest_path=tmp_path / "manifest.json",
    )


def make_input(tmp_path):
    input_path = tmp_path / "input" / "peppa-001.mp4"
    input_path.parent.mkdir()
    input_path.write_text("video")
    return input_path


def manifest_step(settings, slug, step):
    manifest = json.loads(settings.manifest_path.read_text(encoding="utf-8"))
    return manifest["episodes"][slug]["steps"][step]


def test_episode_processor_writes_artifacts_and_outputs(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
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


def test_episode_processor_reuses_existing_artifacts_without_openai_or_media_calls(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    first_media = FakeMediaRunner()
    first_paths = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=first_media).process(input_path)
    mtimes = {
        "normalized": first_paths.normalized_cues_path.stat().st_mtime_ns,
        "pinyin": first_paths.pinyin_subtitle_path.stat().st_mtime_ns,
        "alternating": first_paths.alternating_subtitle_path.stat().st_mtime_ns,
        "mode1": first_paths.mode1_path.stat().st_mtime_ns,
        "mode2": first_paths.mode2_path.stat().st_mtime_ns,
        "mode3": first_paths.mode3_path.stat().st_mtime_ns,
    }
    second_media = FakeMediaRunner()

    second_paths = EpisodeProcessor(settings=settings, openai=FailingOpenAI(), media=second_media).process(input_path)

    assert second_media.calls == []
    assert second_paths.normalized_cues_path.stat().st_mtime_ns == mtimes["normalized"]
    assert second_paths.pinyin_subtitle_path.stat().st_mtime_ns == mtimes["pinyin"]
    assert second_paths.alternating_subtitle_path.stat().st_mtime_ns == mtimes["alternating"]
    assert second_paths.mode1_path.stat().st_mtime_ns == mtimes["mode1"]
    assert second_paths.mode2_path.stat().st_mtime_ns == mtimes["mode2"]
    assert second_paths.mode3_path.stat().st_mtime_ns == mtimes["mode3"]


def test_episode_processor_enriches_existing_english_cues_missing_pinyin(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    processor = EpisodeProcessor(settings=settings, openai=FailingOpenAI(), media=FakeMediaRunner())
    paths = processor.process_paths(input_path)
    paths.ensure_directories()
    paths.audio_path.write_text("audio")
    paths.raw_transcript_path.write_text(json.dumps({"segments": []}), encoding="utf-8")
    paths.mode1_path.write_text("mode1")
    paths.mode2_path.write_text("mode2")
    paths.mode3_path.write_text("mode3")
    paths.normalized_cues_path.write_text(
        json.dumps(
            [
                {
                    "index": 1,
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "A",
                    "chinese": "你好",
                    "pinyin": None,
                    "english": "Hello",
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    processor.process(input_path)

    cues = json.loads(paths.normalized_cues_path.read_text(encoding="utf-8"))
    assert cues[0]["pinyin"] == "nǐ hǎo"
    assert "nǐ hǎo" in paths.pinyin_subtitle_path.read_text(encoding="utf-8")


def test_episode_processor_rerenders_modes_when_existing_subtitles_are_rewritten(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    media = FakeMediaRunner()
    processor = EpisodeProcessor(settings=settings, openai=FailingOpenAI(), media=media)
    paths = processor.process_paths(input_path)
    paths.ensure_directories()
    paths.audio_path.write_text("audio")
    paths.raw_transcript_path.write_text(json.dumps({"segments": []}), encoding="utf-8")
    paths.mode1_path.write_text("mode1")
    paths.pinyin_subtitle_path.write_text("stale pinyin", encoding="utf-8")
    paths.alternating_subtitle_path.write_text("stale alternating", encoding="utf-8")
    paths.mode2_path.write_text("stale mode2")
    paths.mode3_path.write_text("stale mode3")
    paths.normalized_cues_path.write_text(
        json.dumps(
            [
                {
                    "index": 1,
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "A",
                    "chinese": "你好",
                    "pinyin": None,
                    "english": "Hello",
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    processor.process(input_path)

    burn_calls = [call for call in media.calls if call[0] == "burn_subtitles"]
    assert burn_calls == [
        ("burn_subtitles", input_path, paths.pinyin_subtitle_path, paths.mode2_path),
        ("burn_subtitles", input_path, paths.alternating_subtitle_path, paths.mode3_path),
    ]
    assert paths.mode2_path.read_text() == "rendered"
    assert paths.mode3_path.read_text() == "rendered"


def test_episode_processor_deletes_stale_mode2_when_pinyin_rewrite_is_followed_by_failure(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    paths = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=FakeMediaRunner()).process_paths(input_path)
    paths.ensure_directories()
    paths.audio_path.write_text("audio")
    paths.raw_transcript_path.write_text(json.dumps({"segments": []}), encoding="utf-8")
    paths.mode1_path.write_text("mode1")
    paths.pinyin_subtitle_path.write_text("stale pinyin", encoding="utf-8")
    paths.mode2_path.write_text("stale mode2")
    paths.normalized_cues_path.write_text(
        json.dumps(
            [
                {
                    "index": 1,
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "A",
                    "chinese": "你好",
                    "pinyin": None,
                    "english": None,
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="translation unavailable"):
        EpisodeProcessor(settings=settings, openai=TranslationErrorOpenAI(), media=FakeMediaRunner()).process(input_path)

    assert not paths.mode2_path.exists()

    media = FakeMediaRunner()
    EpisodeProcessor(settings=settings, openai=FakeOpenAI(translations={1: "Hello"}), media=media).process(input_path)

    assert ("render_mode1", input_path, paths.mode1_path) not in media.calls
    assert not any(call[0] == "extract_audio" for call in media.calls)
    assert ("burn_subtitles", input_path, paths.pinyin_subtitle_path, paths.mode2_path) in media.calls
    assert paths.mode2_path.read_text() == "rendered"


def test_episode_processor_failed_subtitle_write_leaves_no_partial_and_resumes_rerender(
    tmp_path, monkeypatch
):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    paths = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=FakeMediaRunner()).process_paths(input_path)
    paths.ensure_directories()
    paths.audio_path.write_text("audio")
    paths.raw_transcript_path.write_text(json.dumps({"segments": []}), encoding="utf-8")
    paths.mode1_path.write_text("mode1")
    paths.pinyin_subtitle_path.write_text("stale pinyin subtitle", encoding="utf-8")
    paths.mode2_path.write_text("stale mode2")
    paths.alternating_subtitle_path.write_text("existing alternating", encoding="utf-8")
    paths.normalized_cues_path.write_text(
        json.dumps(
            [
                {
                    "index": 1,
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "A",
                    "chinese": "你好",
                    "pinyin": None,
                    "english": "Hello",
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    def failing_write_ass(path, cues, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("partial subtitle", encoding="utf-8")
        if mode == "pinyin":
            raise RuntimeError("subtitle write failed")
        real_write_ass(path, cues, mode=mode)

    monkeypatch.setattr(pipeline_module, "write_ass", failing_write_ass)

    with pytest.raises(RuntimeError, match="subtitle write failed"):
        EpisodeProcessor(settings=settings, openai=FailingOpenAI(), media=FakeMediaRunner()).process(input_path)

    assert not paths.pinyin_subtitle_path.exists()
    assert not paths.mode2_path.exists()

    monkeypatch.setattr(pipeline_module, "write_ass", real_write_ass)
    media = FakeMediaRunner()
    EpisodeProcessor(settings=settings, openai=FailingOpenAI(), media=media).process(input_path)

    assert "partial subtitle" not in paths.pinyin_subtitle_path.read_text(encoding="utf-8")
    assert ("burn_subtitles", input_path, paths.pinyin_subtitle_path, paths.mode2_path) in media.calls
    assert paths.mode2_path.read_text() == "rendered"


def test_episode_processor_failed_alternating_rewrite_removes_stale_subtitle_and_mode3(
    tmp_path, monkeypatch
):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    paths = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=FakeMediaRunner()).process_paths(input_path)
    paths.ensure_directories()
    paths.audio_path.write_text("audio")
    paths.raw_transcript_path.write_text(json.dumps({"segments": []}), encoding="utf-8")
    paths.mode1_path.write_text("mode1")
    paths.pinyin_subtitle_path.write_text("existing pinyin", encoding="utf-8")
    paths.alternating_subtitle_path.write_text("stale alternating", encoding="utf-8")
    paths.mode3_path.write_text("stale mode3")
    paths.normalized_cues_path.write_text(
        json.dumps(
            [
                {
                    "index": 1,
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "A",
                    "chinese": "你好",
                    "pinyin": "nǐ hǎo",
                    "english": None,
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    def failing_write_ass(path, cues, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("partial subtitle", encoding="utf-8")
        if mode == "alternating":
            raise RuntimeError("alternating subtitle write failed")
        real_write_ass(path, cues, mode=mode)

    monkeypatch.setattr(pipeline_module, "write_ass", failing_write_ass)

    with pytest.raises(RuntimeError, match="alternating subtitle write failed"):
        EpisodeProcessor(
            settings=settings,
            openai=FakeOpenAI(translations={1: "Hello"}),
            media=FakeMediaRunner(),
        ).process(input_path)

    assert not paths.alternating_subtitle_path.exists()
    assert not paths.mode3_path.exists()


def test_episode_processor_rejects_missing_translation_index_and_records_failure(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    processor = EpisodeProcessor(settings=settings, openai=FakeOpenAI(translations={1: "Hello"}), media=FakeMediaRunner())

    with pytest.raises(ValueError, match="Translation indexes do not match cue indexes"):
        processor.process(input_path)

    paths = processor.process_paths(input_path)
    cues = json.loads(paths.normalized_cues_path.read_text(encoding="utf-8"))
    assert [cue["english"] for cue in cues] == [None, None]
    assert manifest_step(settings, paths.slug, "build_cues")["status"] == "failed"
    assert "Translation indexes do not match cue indexes" in manifest_step(settings, paths.slug, "build_cues")["error"]


def test_episode_processor_translation_failure_preserves_pinyin_artifacts_and_records_failure(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    processor = EpisodeProcessor(settings=settings, openai=TranslationErrorOpenAI(), media=FakeMediaRunner())

    with pytest.raises(RuntimeError, match="translation unavailable"):
        processor.process(input_path)

    paths = processor.process_paths(input_path)
    cues = json.loads(paths.normalized_cues_path.read_text(encoding="utf-8"))
    assert paths.raw_transcript_path.exists()
    assert paths.pinyin_subtitle_path.exists()
    assert all(cue["pinyin"] for cue in cues)
    assert [cue["english"] for cue in cues] == [None, None]
    assert manifest_step(settings, paths.slug, "build_cues")["status"] == "failed"
    assert manifest_step(settings, paths.slug, "build_cues")["error"] == "translation unavailable"


def test_episode_processor_resumes_after_translation_failure_without_rerunning_early_stages(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    first_media = FakeMediaRunner()

    with pytest.raises(RuntimeError, match="translation unavailable"):
        EpisodeProcessor(settings=settings, openai=TranslationErrorOpenAI(), media=first_media).process(input_path)

    openai = FakeOpenAI()
    second_media = FakeMediaRunner()
    paths = EpisodeProcessor(settings=settings, openai=openai, media=second_media).process(input_path)
    cues = json.loads(paths.normalized_cues_path.read_text(encoding="utf-8"))

    assert openai.transcribe_calls == 0
    assert openai.translate_calls == 1
    assert "render_mode1" not in [call[0] for call in second_media.calls]
    assert "extract_audio" not in [call[0] for call in second_media.calls]
    assert all(cue["pinyin"] for cue in cues)
    assert all(cue["english"] for cue in cues)
    assert paths.mode2_path.read_text() == "rendered"
    assert paths.mode3_path.read_text() == "rendered"


def test_episode_processor_render_failure_records_manifest_failure(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    media = FailingRenderMediaRunner()
    processor = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=media)

    with pytest.raises(RuntimeError, match="render failed"):
        processor.process(input_path)

    paths = processor.process_paths(input_path)
    assert manifest_step(settings, paths.slug, "render_mode2")["status"] == "failed"
    assert manifest_step(settings, paths.slug, "render_mode2")["error"] == "render failed"


def test_episode_processor_deletes_partial_mode2_and_resume_rerenders(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    first_processor = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=PartialMode2MediaRunner())

    with pytest.raises(RuntimeError, match="mode2 failed"):
        first_processor.process(input_path)

    paths = first_processor.process_paths(input_path)
    assert not paths.mode2_path.exists()
    assert manifest_step(settings, paths.slug, "render_mode2")["status"] == "failed"

    media = FakeMediaRunner()
    EpisodeProcessor(settings=settings, openai=FailingOpenAI(), media=media).process(input_path)

    assert ("burn_subtitles", input_path, paths.pinyin_subtitle_path, paths.mode2_path) in media.calls
    assert paths.mode2_path.read_text() == "rendered"


def test_episode_processor_deletes_partial_mode3_on_render_failure(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    processor = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=PartialMode3MediaRunner())

    with pytest.raises(RuntimeError, match="mode3 failed"):
        processor.process(input_path)

    paths = processor.process_paths(input_path)
    assert paths.mode2_path.exists()
    assert not paths.mode3_path.exists()
    assert manifest_step(settings, paths.slug, "render_mode3")["status"] == "failed"


def test_episode_processor_deletes_partial_mode1_and_audio_on_failure(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    mode1_processor = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=PartialMode1MediaRunner())

    with pytest.raises(RuntimeError, match="mode1 failed"):
        mode1_processor.process(input_path)

    paths = mode1_processor.process_paths(input_path)
    assert not paths.mode1_path.exists()
    assert manifest_step(settings, paths.slug, "render_mode1")["status"] == "failed"

    audio_tmp_path = tmp_path / "audio_case"
    audio_tmp_path.mkdir()
    settings = make_settings(audio_tmp_path)
    input_path = make_input(audio_tmp_path)
    audio_processor = EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=PartialAudioMediaRunner())

    with pytest.raises(RuntimeError, match="audio failed"):
        audio_processor.process(input_path)

    paths = audio_processor.process_paths(input_path)
    assert not paths.audio_path.exists()
    assert manifest_step(settings, paths.slug, "extract_audio")["status"] == "failed"


def test_episode_processor_force_reruns_existing_stages(tmp_path):
    input_path = make_input(tmp_path)
    settings = make_settings(tmp_path)
    EpisodeProcessor(settings=settings, openai=FakeOpenAI(), media=FakeMediaRunner()).process(input_path)
    openai = FakeOpenAI()
    media = FakeMediaRunner()

    EpisodeProcessor(settings=settings, openai=openai, media=media).process(input_path, force=True)

    assert openai.transcribe_calls == 1
    assert openai.translate_calls == 1
    assert [call[0] for call in media.calls] == [
        "render_mode1",
        "extract_audio",
        "burn_subtitles",
        "burn_subtitles",
    ]
