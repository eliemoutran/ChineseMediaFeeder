from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import httpx


class TelegramApiError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str, http_client: Any | None = None) -> None:
        self.token = token
        self.http_client = http_client or httpx.Client()
        self._owns_http_client = http_client is None or hasattr(http_client, "close")

    def send_message(self, chat_id: str, text: str) -> dict[str, Any]:
        payload = self._post("sendMessage", data={"chat_id": chat_id, "text": text})
        return dict(payload.get("result") or {})

    def send_video(self, chat_id: str, video_path: Path, caption: str) -> dict[str, Any]:
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "supports_streaming": "true",
        }
        dimensions = probe_video_dimensions(video_path)
        if dimensions is not None:
            width, height = dimensions
            data["width"] = str(width)
            data["height"] = str(height)

        with video_path.open("rb") as video_file:
            payload = self._post(
                "sendVideo",
                data=data,
                files={"video": (video_path.name, video_file, "video/mp4")},
                timeout=300,
            )
        return dict(payload.get("result") or {})

    def close(self) -> None:
        close = getattr(self.http_client, "close", None)
        if close is not None:
            close()

    def _post(
        self,
        method: str,
        data: dict[str, str],
        files: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        response = self.http_client.post(
            f"https://api.telegram.org/bot{self.token}/{method}",
            data=data,
            files=files,
            timeout=timeout,
        )
        payload = response.json()
        if response.status_code >= 400 or not payload.get("ok"):
            description = payload.get("description") or f"Telegram API error {response.status_code}"
            raise TelegramApiError(str(description))
        return dict(payload)


def probe_video_dimensions(video_path: Path) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(video_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        streams = json.loads(result.stdout).get("streams") or []
        if not streams:
            return None
        width = int(streams[0]["width"])
        height = int(streams[0]["height"])
    except (OSError, subprocess.CalledProcessError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height
