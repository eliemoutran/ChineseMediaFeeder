from pathlib import Path

import pytest

from chinese_media_feeder.schedule import (
    MissingScheduleOutputError,
    build_day_schedule,
    resolve_schedule_outputs,
)


def test_build_day_schedule_starts_with_new_no_sub_episode():
    items = build_day_schedule(day=1)

    assert [(item.episode_number, item.mode) for item in items] == [(1, 1)]
    assert items[0].emoji == "📺"


def test_build_day_schedule_fills_rotation_by_day_six():
    items = build_day_schedule(day=6)

    assert [(item.episode_number, item.mode) for item in items] == [
        (6, 1),
        (5, 2),
        (4, 3),
        (1, 4),
    ]
    assert [item.emoji for item in items] == ["📺", "🔁", "🔁", "🎯"]


def test_build_day_schedule_rejects_invalid_day():
    with pytest.raises(ValueError, match="day must be at least 1"):
        build_day_schedule(day=0)


def test_resolve_schedule_outputs_maps_modes_to_existing_files_and_aliases_mode4(tmp_path):
    output_dir = tmp_path / "output"
    ep1 = output_dir / "peppa-001"
    ep2 = output_dir / "peppa-002"
    ep1.mkdir(parents=True)
    ep2.mkdir(parents=True)
    mode1 = ep1 / "peppa-001.mode1-nosubs.mp4"
    mode2 = ep2 / "peppa-002.mode2-pinyin.mp4"
    mode1.write_text("video")
    mode2.write_text("video")

    resolved = resolve_schedule_outputs(
        [
            build_day_schedule(day=1)[0],
            build_day_schedule(day=3)[1],
            build_day_schedule(day=6)[3],
        ],
        output_dir=output_dir,
    )

    assert [item.path for item in resolved] == [mode1, mode2, mode1]
    assert resolved[2].mode == 4
    assert resolved[2].source_mode == 1


def test_resolve_schedule_outputs_reports_missing_episode_and_mode(tmp_path):
    output_dir = tmp_path / "output"
    ep1 = output_dir / "peppa-001"
    ep1.mkdir(parents=True)
    (ep1 / "peppa-001.mode1-nosubs.mp4").write_text("video")

    with pytest.raises(MissingScheduleOutputError) as exc_info:
        resolve_schedule_outputs(build_day_schedule(day=3), output_dir=output_dir)

    message = str(exc_info.value)
    assert "episode 3 mode 1" in message
    assert "episode 2 mode 2" in message
