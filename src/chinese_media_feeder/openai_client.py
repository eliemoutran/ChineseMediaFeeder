from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from openai import OpenAI

from chinese_media_feeder.cues import Cue
from chinese_media_feeder.transcripts import build_timing_primary_transcript


MANDARIN_ACCURACY_PROMPT = (
    "The audio is Mandarin Chinese from a children's cartoon. "
    "Transcribe all Mandarin speech with high accuracy. "
    "Keep the text in simplified Chinese characters and do not translate."
)
TRANSLATION_BATCH_SIZE = 40
T = TypeVar("T")


class OpenAIAdapterError(RuntimeError):
    pass


class OpenAIAdapter:
    def __init__(
        self,
        api_key: str,
        transcribe_model: str,
        translation_model: str,
        client=None,
        timing_transcribe_model: str = "whisper-1",
    ) -> None:
        self.client = client if client is not None else OpenAI(api_key=api_key)
        self.transcribe_model = transcribe_model
        self.timing_transcribe_model = timing_transcribe_model
        self.translation_model = translation_model

    def transcribe(self, audio_path: Path) -> dict:
        timing_transcript = self._transcribe_timing(audio_path)
        diarized_transcript = self._transcribe_diarized(audio_path)
        return build_timing_primary_transcript(timing_transcript, diarized_transcript)

    def _transcribe_timing(self, audio_path: Path) -> dict:
        with audio_path.open("rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model=self.timing_transcribe_model,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment", "word"],
                language="zh",
                temperature=0,
                prompt=MANDARIN_ACCURACY_PROMPT,
            )
        return _response_to_dict(response)

    def _transcribe_diarized(self, audio_path: Path) -> dict:
        with audio_path.open("rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model=self.transcribe_model,
                file=audio_file,
                response_format="diarized_json",
                chunking_strategy="auto",
                language="zh",
                temperature=0,
            )
        return _response_to_dict(response)

    def translate_cues(self, cues: list[Cue]) -> dict[int, str]:
        if not cues:
            return {}

        translations: dict[int, str] = {}
        for batch in _chunks(cues, TRANSLATION_BATCH_SIZE):
            translations.update(self._translate_cue_batch(batch))
        self._require_exact_indexes(translations, {cue.index for cue in cues})
        return translations

    def _translate_cue_batch(self, cues: list[Cue]) -> dict[int, str]:
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
        data = self._parse_translation_response(response)
        translations = self._validate_translations(data)
        self._require_exact_indexes(translations, {cue.index for cue in cues})
        return translations

    def _parse_translation_response(self, response) -> dict:
        try:
            output_text = response.output_text
        except AttributeError as exc:
            raise OpenAIAdapterError("OpenAI translation response is missing output_text.") from exc

        try:
            data = json.loads(output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise OpenAIAdapterError("OpenAI translation response output_text must contain valid JSON.") from exc

        if not isinstance(data, dict):
            raise OpenAIAdapterError("OpenAI translation response JSON must be an object.")
        return data

    def _validate_translations(self, data: dict) -> dict[int, str]:
        translations = data.get("translations")
        if not isinstance(translations, list):
            raise OpenAIAdapterError("OpenAI translation response must include a translations list.")

        parsed: dict[int, str] = {}
        for item in translations:
            if not isinstance(item, dict):
                raise OpenAIAdapterError("Each translation item must be an object.")
            if "index" not in item:
                raise OpenAIAdapterError("Each translation item must include an index.")
            if "english" not in item:
                raise OpenAIAdapterError("Each translation item must include english text.")

            index = item["index"]
            if type(index) is not int:
                raise OpenAIAdapterError("Each translation index must be an integer.")

            english = item["english"]
            if not isinstance(english, str):
                raise OpenAIAdapterError("Each translation english value must be a string.")
            if index in parsed:
                raise OpenAIAdapterError(f"Duplicate translation index returned: {index}.")
            parsed[index] = english

        return parsed

    def _require_exact_indexes(self, translations: dict[int, str], expected_indexes: set[int]) -> None:
        returned_indexes = set(translations)
        missing = expected_indexes - returned_indexes
        extra = returned_indexes - expected_indexes
        if missing:
            raise OpenAIAdapterError(f"OpenAI translation response is missing indexes: {sorted(missing)}.")
        if extra:
            raise OpenAIAdapterError(f"OpenAI translation response included extra indexes: {sorted(extra)}.")


def _response_to_dict(response) -> dict:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if isinstance(response, dict):
        return response
    return json.loads(response)


def _chunks(items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]
