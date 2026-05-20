from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ManifestStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"episodes": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def update_step(
        self,
        slug: str,
        input_path: Path,
        step: str,
        status: str,
        artifacts: dict[str, Path] | None = None,
        outputs: dict[str, Path] | None = None,
        models: dict[str, str] | None = None,
        error: str | None = None,
    ) -> None:
        data = self.load()
        updated_at = _now_iso()
        episode = data["episodes"].setdefault(slug, {})
        episode["input_path"] = _path_to_manifest(input_path)
        episode.setdefault("steps", {})
        episode.setdefault("artifacts", {})
        episode.setdefault("outputs", {})
        episode.setdefault("models", {})
        episode["steps"][step] = {
            "status": status,
            "updated_at": updated_at,
        }
        if error:
            episode["steps"][step]["error"] = error
        for key, value in (artifacts or {}).items():
            episode["artifacts"][key] = _path_to_manifest(value)
        for key, value in (outputs or {}).items():
            episode["outputs"][key] = _path_to_manifest(value)
        for key, value in (models or {}).items():
            episode["models"][key] = value
        episode["updated_at"] = updated_at
        self.save(data)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _path_to_manifest(path: Path) -> str:
    return path.as_posix()
