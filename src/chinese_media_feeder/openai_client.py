from __future__ import annotations

import json
from pathlib import Path

from openai import OpenAI

from chinese_media_feeder.cues import Cue


class OpenAIAdapterError(RuntimeError):
    pass


class OpenAIAdapter:
    def __init__(self, api_key: str, transcribe_model: str, translation_model: str, client=None) -> None:
        self.client = client if client is not None else OpenAI(api_key=api_key)
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
        if not cues:
            return {}

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

            try:
                index = int(item["index"])
            except (TypeError, ValueError) as exc:
                raise OpenAIAdapterError("Each translation index must be integer-compatible.") from exc

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
