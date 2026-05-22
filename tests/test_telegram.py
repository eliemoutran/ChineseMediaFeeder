import subprocess
from pathlib import Path

import pytest

import chinese_media_feeder.telegram as telegram_module
from chinese_media_feeder.telegram import TelegramApiError, TelegramClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, response):
        self.response = response
        self.posts = []
        self.closed = False

    def post(self, url, data=None, files=None, timeout=None):
        self.posts.append({"url": url, "data": data, "files": files, "timeout": timeout})
        return self.response

    def close(self):
        self.closed = True


def test_send_message_posts_to_telegram_api():
    http = FakeHttpClient(FakeResponse({"ok": True, "result": {"message_id": 1}}))
    client = TelegramClient(token="token", http_client=http)

    result = client.send_message(chat_id="123", text="hello")

    assert result == {"message_id": 1}
    assert http.posts[0]["url"] == "https://api.telegram.org/bottoken/sendMessage"
    assert http.posts[0]["data"] == {"chat_id": "123", "text": "hello"}


def test_send_message_supports_inline_keyboard_reply_markup():
    http = FakeHttpClient(FakeResponse({"ok": True, "result": {"message_id": 1}}))
    client = TelegramClient(token="token", http_client=http)
    keyboard = {"inline_keyboard": [[{"text": "Watched", "callback_data": "watched:1:0"}]]}

    client.send_message(chat_id="123", text="hello", reply_markup=keyboard)

    assert http.posts[0]["data"]["reply_markup"] == (
        '{"inline_keyboard":[[{"text":"Watched","callback_data":"watched:1:0"}]]}'
    )


def test_send_video_uploads_file_with_caption_and_dimensions(tmp_path, monkeypatch):
    video = tmp_path / "episode.mp4"
    video.write_bytes(b"video")
    http = FakeHttpClient(FakeResponse({"ok": True, "result": {"message_id": 2}}))
    client = TelegramClient(token="token", http_client=http)
    monkeypatch.setattr(telegram_module, "probe_video_dimensions", lambda path: (1920, 1080))

    keyboard = {"inline_keyboard": [[{"text": "Watched", "callback_data": "watched:1:0"}]]}

    result = client.send_video(chat_id="123", video_path=video, caption="caption", reply_markup=keyboard)

    assert result == {"message_id": 2}
    post = http.posts[0]
    assert post["url"] == "https://api.telegram.org/bottoken/sendVideo"
    assert post["data"] == {
        "chat_id": "123",
        "caption": "caption",
        "supports_streaming": "true",
        "width": "1920",
        "height": "1080",
        "reply_markup": '{"inline_keyboard":[[{"text":"Watched","callback_data":"watched:1:0"}]]}',
    }
    assert post["files"]["video"][0] == "episode.mp4"
    assert http.closed is False


def test_send_video_omits_dimensions_when_probe_fails(tmp_path, monkeypatch):
    video = tmp_path / "episode.mp4"
    video.write_bytes(b"video")
    http = FakeHttpClient(FakeResponse({"ok": True, "result": {"message_id": 2}}))
    client = TelegramClient(token="token", http_client=http)
    monkeypatch.setattr(telegram_module, "probe_video_dimensions", lambda path: None)

    client.send_video(chat_id="123", video_path=video, caption="caption")

    assert "width" not in http.posts[0]["data"]
    assert "height" not in http.posts[0]["data"]


def test_probe_video_dimensions_parses_ffprobe_json(monkeypatch, tmp_path):
    video = tmp_path / "episode.mp4"
    video.write_bytes(b"video")

    def fake_run(command, check, capture_output, text):
        assert command[:4] == ["ffprobe", "-v", "error", "-select_streams"]
        assert command[-1] == str(video)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"streams":[{"width":1920,"height":1080}]}',
            stderr="",
        )

    monkeypatch.setattr(telegram_module.subprocess, "run", fake_run)

    assert telegram_module.probe_video_dimensions(video) == (1920, 1080)


def test_telegram_client_raises_for_not_ok_response():
    http = FakeHttpClient(FakeResponse({"ok": False, "description": "bad chat"}, status_code=400))
    client = TelegramClient(token="token", http_client=http)

    with pytest.raises(TelegramApiError, match="bad chat"):
        client.send_message(chat_id="123", text="hello")


def test_get_updates_posts_offset_and_timeout():
    http = FakeHttpClient(FakeResponse({"ok": True, "result": [{"update_id": 11}]}))
    client = TelegramClient(token="token", http_client=http)

    updates = client.get_updates(offset=10, timeout=25)

    assert updates == [{"update_id": 11}]
    assert http.posts[0]["url"] == "https://api.telegram.org/bottoken/getUpdates"
    assert http.posts[0]["data"] == {"offset": "10", "timeout": "25"}


def test_answer_callback_query_posts_callback_id_and_text():
    http = FakeHttpClient(FakeResponse({"ok": True, "result": True}))
    client = TelegramClient(token="token", http_client=http)

    client.answer_callback_query(callback_query_id="abc", text="Recorded")

    assert http.posts[0]["url"] == "https://api.telegram.org/bottoken/answerCallbackQuery"
    assert http.posts[0]["data"] == {"callback_query_id": "abc", "text": "Recorded"}


def test_telegram_client_closes_owned_http_client():
    http = FakeHttpClient(FakeResponse({"ok": True, "result": {}}))
    client = TelegramClient(token="token", http_client=http)

    client.close()

    assert http.closed is True
