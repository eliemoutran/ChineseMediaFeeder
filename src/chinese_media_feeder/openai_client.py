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
