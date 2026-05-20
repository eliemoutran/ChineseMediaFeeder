from __future__ import annotations

import json

import pytest

from chinese_media_feeder.cues import Cue
from chinese_media_feeder.openai_client import OpenAIAdapter, OpenAIAdapterError


class FakeModelDumpResponse:
    def __init__(self, data: dict) -> None:
        self.data = data

    def model_dump(self) -> dict:
        return self.data


class FakeTranscriptions:
    def __init__(self, responses: object | list[object]) -> None:
        self.responses = list(responses) if isinstance(responses, list) else [responses]
        self.calls: list[dict] = []

    def create(self, **kwargs) -> object:
        self.calls.append(kwargs)
        assert not kwargs["file"].closed
        return self.responses.pop(0)


class FakeAudio:
    def __init__(self, response: object) -> None:
        self.transcriptions = FakeTranscriptions(response)


class FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict] = []

    def create(self, **kwargs) -> object:
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(
        self,
        transcription_response: object | None = None,
        translation_response: object | None = None,
    ) -> None:
        self.audio = FakeAudio(transcription_response)
        self.responses = FakeResponses(translation_response)


class FakeOutputTextResponse:
    def __init__(self, output_text: str | None) -> None:
        self.output_text = output_text


def make_cue(index: int, chinese: str) -> Cue:
    return Cue(index=index, start=0.0, end=1.0, speaker="SPEAKER_00", chinese=chinese)


def make_adapter(client: FakeClient) -> OpenAIAdapter:
    return OpenAIAdapter(
        api_key="test-key",
        transcribe_model="whisper-test",
        translation_model="gpt-test",
        client=client,
    )


def test_transcribe_runs_timing_pass_then_diarized_pass(tmp_path):
    timing_data = {"segments": [{"start": 0.0, "end": 1.0, "text": "ä½ å¥½"}]}
    diarized_data = {"diarized_segments": [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "ä½ å¥½"}]}
    client = FakeClient(
        transcription_response=[
            FakeModelDumpResponse(timing_data),
            FakeModelDumpResponse(diarized_data),
        ]
    )
    adapter = make_adapter(client)
    audio_path = tmp_path / "audio.m4a"
    audio_path.write_bytes(b"fake audio")

    result = adapter.transcribe(audio_path)

    assert result["segments"] == [
        {
            "start": 0.0,
            "end": 1.0,
            "text": "ä½ å¥½",
            "speaker": "SPEAKER_00",
            "diarized_text": "ä½ å¥½",
        }
    ]
    assert result["timing_transcript"] == timing_data
    assert result["diarized_transcript"] == diarized_data
    assert len(client.audio.transcriptions.calls) == 2

    timing_call = client.audio.transcriptions.calls[0]
    assert timing_call["model"] == "whisper-1"
    assert timing_call["file"].name == str(audio_path)
    assert timing_call["file"].closed
    assert timing_call["response_format"] == "verbose_json"
    assert timing_call["timestamp_granularities"] == ["segment"]
    assert timing_call["language"] == "zh"
    assert timing_call["temperature"] == 0
    assert "Mandarin Chinese" in timing_call["prompt"]
    assert "high accuracy" in timing_call["prompt"]
    assert "chunking_strategy" not in timing_call

    diarized_call = client.audio.transcriptions.calls[1]
    assert diarized_call["model"] == "whisper-test"
    assert diarized_call["file"].name == str(audio_path)
    assert diarized_call["file"].closed
    assert diarized_call["response_format"] == "diarized_json"
    assert diarized_call["chunking_strategy"] == "auto"
    assert diarized_call["language"] == "zh"
    assert diarized_call["temperature"] == 0
    assert "prompt" not in diarized_call


def test_translate_cues_sends_strict_schema_and_preserves_chinese_json():
    response = FakeOutputTextResponse(
        json.dumps(
            {"translations": [{"index": 1, "english": "Hello, Peppa."}, {"index": 2, "english": "I'm here."}]}
        )
    )
    client = FakeClient(translation_response=response)
    adapter = make_adapter(client)

    translations = adapter.translate_cues([make_cue(1, "你好，佩奇。"), make_cue(2, "我来了。")])

    assert translations == {1: "Hello, Peppa.", 2: "I'm here."}
    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    assert call["model"] == "gpt-test"
    assert call["text"]["format"]["strict"] is True
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["schema"]["required"] == ["translations"]
    user_message = call["input"][1]
    assert user_message["role"] == "user"
    assert "你好，佩奇。" in user_message["content"]
    assert "\\u4f60" not in user_message["content"]
    assert json.loads(user_message["content"]) == {
        "cues": [{"index": 1, "chinese": "你好，佩奇。"}, {"index": 2, "chinese": "我来了。"}]
    }


def test_translate_cues_empty_input_returns_empty_dict_without_api_call():
    client = FakeClient(translation_response=FakeOutputTextResponse('{"translations": []}'))
    adapter = make_adapter(client)

    assert adapter.translate_cues([]) == {}
    assert client.responses.calls == []


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeOutputTextResponse("{not-json"), "valid JSON"),
        (FakeOutputTextResponse(None), "valid JSON"),
        (object(), "output_text"),
        (FakeOutputTextResponse('{"items": []}'), "translations"),
        (FakeOutputTextResponse('{"translations": {}}'), "translations"),
        (FakeOutputTextResponse('{"translations": [{"index": 1}]}'), "english"),
        (FakeOutputTextResponse('{"translations": [{"index": 1, "english": 42}]}'), "english"),
        (FakeOutputTextResponse('{"translations": [{"index": "abc", "english": "Hello."}]}'), "index"),
        (FakeOutputTextResponse('{"translations": [{"index": "1", "english": "Hello."}]}'), "index"),
        (FakeOutputTextResponse('{"translations": [{"index": 1.0, "english": "Hello."}]}'), "index"),
        (FakeOutputTextResponse('{"translations": [{"index": true, "english": "Hello."}]}'), "index"),
    ],
)
def test_translate_cues_rejects_malformed_translation_response(response, message):
    adapter = make_adapter(FakeClient(translation_response=response))

    with pytest.raises(OpenAIAdapterError, match=message):
        adapter.translate_cues([make_cue(1, "你好。")])


@pytest.mark.parametrize(
    ("translations", "message"),
    [
        ([{"index": 1, "english": "Hello."}], "missing"),
        ([{"index": 1, "english": "Hello."}, {"index": 2, "english": "Hi."}, {"index": 3, "english": "Extra."}], "extra"),
        ([{"index": 1, "english": "Hello."}, {"index": 1, "english": "Again."}], "Duplicate"),
    ],
)
def test_translate_cues_requires_exact_translation_indexes(translations, message):
    response = FakeOutputTextResponse(json.dumps({"translations": translations}))
    adapter = make_adapter(FakeClient(translation_response=response))

    with pytest.raises(OpenAIAdapterError, match=message):
        adapter.translate_cues([make_cue(1, "你好。"), make_cue(2, "我来了。")])
