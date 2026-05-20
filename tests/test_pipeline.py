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
