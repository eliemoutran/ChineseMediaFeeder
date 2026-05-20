# V1 Media Generator Design

## Overview

ChineseMediaFeeder V1 generates learner-focused MP4 variants from local Mandarin episode files. The goal is to prove the media pipeline before building Telegram delivery. The system accepts local video files, transcribes the Mandarin speech with OpenAI, creates pinyin and English learning subtitles, and renders three MP4 outputs per episode.

Telegram scheduling and YouTube playlist ingestion are out of scope for V1. The output naming and manifest format should still make those later features straightforward to consume.

## Goals

- Process local episode files from `media/input/`.
- Generate three MP4 files per episode:
  - Mode 1: no subtitles.
  - Mode 2: pinyin-only subtitles.
  - Mode 3: alternating pinyin and English subtitles.
- Use OpenAI cloud services for transcription and translation.
- Use local code for pinyin conversion and video rendering.
- Save intermediate artifacts so failed steps can be retried without starting over.
- Run as a local CLI first, while keeping the project Docker-friendly for later VPS use.

## Non-Goals

- No Telegram bot or daily spaced-repetition scheduler in V1.
- No YouTube playlist ingestion in V1.
- No web UI in V1.
- No manual transcript editor in V1.
- No fully local speech model path in V1.

## Architecture

V1 is a Python CLI application with clear pipeline stages. The CLI owns orchestration, while focused modules handle media operations, OpenAI calls, subtitle construction, pinyin conversion, translation, manifest updates, and rendering.

Expected top-level project shape:

```text
media/
  input/
  output/
  work/
src/
  chinese_media_feeder/
    cli.py
    config.py
    manifest.py
    media.py
    openai_client.py
    pinyin.py
    subtitles.py
    render.py
tests/
```

The implementation can adjust exact filenames if Python packaging conventions require it, but the boundaries should remain stable.

## Data Flow

1. Scan `media/input/` for supported local video files.
2. Create an episode slug from the filename.
3. Create `media/work/<episode_slug>/` and `media/output/<episode_slug>/`.
4. Normalize or copy the source video into Mode 1 output.
5. Extract and compress audio with `ffmpeg`.
6. Send the prepared audio to OpenAI `gpt-4o-transcribe-diarize`.
7. Save raw transcription JSON in the work folder.
8. Convert transcript segments into subtitle cues with start time, end time, speaker label when available, Chinese text, and stable cue index.
9. Generate pinyin text for each Chinese cue with `pypinyin`.
10. Translate each cue into concise learner-friendly English with an OpenAI text model.
11. Save normalized cue JSON and subtitle files.
12. Render Mode 2 and Mode 3 MP4 files with `ffmpeg`.
13. Update the manifest with output paths and processing status.

## Output Contract

For an input file such as `peppa-001.mp4`, the pipeline writes:

```text
media/output/peppa-001/
  peppa-001.mode1-nosubs.mp4
  peppa-001.mode2-pinyin.mp4
  peppa-001.mode3-alternating.mp4
```

Work artifacts are retained under:

```text
media/work/peppa-001/
  audio.m4a
  transcript.raw.json
  cues.normalized.json
  subtitles.pinyin.ass
  subtitles.alternating.ass
```

The manifest is stored at `media/manifest.json` for V1. It records each episode slug, input path, output paths, artifact paths, step status, timestamps, and the selected OpenAI model names. JSON is enough for V1 because the first milestone is a single-user generator; SQLite can replace it when the bot and schedule history require stronger querying.

## Subtitle Modes

Mode 1 is the clean video with no burned-in subtitles. It will later double as the delayed callback-test mode for the Telegram rotation.

Mode 2 burns pinyin subtitles only. The pinyin should preserve Mandarin pronunciation and tone marks. Chinese characters are not shown in the V1 rendered video, although they are retained in work artifacts.

Mode 3 alternates pinyin and English by conversation turn. If diarized speaker labels are available, the alternation should respect speaker or turn boundaries. If speaker labels are missing or unreliable, the pipeline alternates by subtitle cue index. The alternation is deterministic: cue 1 pinyin, cue 2 English, cue 3 pinyin, cue 4 English, and so on. Random ordering is not used because repeat review should be consistent.

English translations should be natural, short, and context-aware. They should help comprehension without becoming overly literal or adult-sounding.

## OpenAI Use

Transcription uses OpenAI `gpt-4o-transcribe-diarize` through the audio transcription API. The implementation should request structured diarized output when available and preserve the raw response before normalization.

Translation uses a configurable OpenAI text model. The V1 default is `gpt-5.4-mini`, chosen as a balance between cost and translation quality for short conversational subtitle cues. The translation prompt should ask for child-friendly conversational English, preserve line count and order, and return machine-readable structured output so each translation maps back to a cue.

OpenAI model names, API key, and retry settings are configuration values. Secrets are read from environment variables and are never written to the manifest or logs.

## Video Rendering

`ffmpeg` is the rendering engine.

The renderer should use `.ass` subtitles rather than plain `.srt` for better control over font size, margins, wrapping, and readability. Subtitle styles should target small-screen Telegram viewing later: high contrast, bottom aligned, and large enough to read on a phone without covering too much of the video.

Mode 1 can be a stream copy if the input is already Telegram-friendly MP4. Otherwise it should normalize to a broadly compatible MP4 container and codec. Modes 2 and 3 burn subtitles into new MP4 files.

## Error Handling and Retry Behavior

Every major stage writes an artifact before the next stage begins. Re-running the CLI should skip completed stages unless the user passes a force option.

Expected failure handling:

- If audio extraction fails, mark the episode as failed at `extract_audio`.
- If OpenAI transcription fails, keep the audio artifact and mark the episode as failed at `transcribe`.
- If translation fails, keep transcript and pinyin artifacts and mark Mode 3 incomplete.
- If rendering fails, keep subtitle files and mark only the failed render step incomplete.
- If the audio file is too large for the transcription upload limit, retry with lower bitrate audio. If it still exceeds the limit, split the audio into chunks and stitch normalized cues by offset.

Failures should be visible in the CLI output and manifest. The CLI should not delete successful artifacts during a failed retry.

## CLI Commands

V1 should expose a small command surface:

```text
cmf scan
cmf process <input-file>
cmf process-all
cmf status
```

`process` handles one video. `process-all` scans the input folder and processes anything not complete. `status` prints episode status from the manifest.

## Configuration

Configuration should come from environment variables and optional `.env` loading:

```text
OPENAI_API_KEY
OPENAI_TRANSCRIBE_MODEL=gpt-4o-transcribe-diarize
OPENAI_TRANSLATION_MODEL=gpt-5.4-mini
MEDIA_INPUT_DIR=media/input
MEDIA_WORK_DIR=media/work
MEDIA_OUTPUT_DIR=media/output
MEDIA_MANIFEST_PATH=media/manifest.json
```

The default translation model may be changed by environment variable without code changes.

## Testing Strategy

Unit tests should cover:

- Episode slug generation and output naming.
- Manifest read/write and status transitions.
- Transcript response normalization into internal cue records.
- Pinyin generation.
- Alternating Mode 3 subtitle selection.
- ASS subtitle escaping and formatting.
- `ffmpeg` command construction.

Integration tests should avoid paid API calls by using fixture transcript JSON. A smoke test should render a tiny generated or fixture video with test subtitles to prove `ffmpeg` wiring works.

Paid OpenAI calls should be behind explicit commands or opt-in test flags.

## Future Versions

V2 can add the Telegram bot and daily rotation:

- Day N: new episode Mode 1.
- Day N-1: Mode 2.
- Day N-2: Mode 3.
- Day N-5: Mode 1 callback test.

Later versions can add YouTube playlist ingestion, cloud object storage, manual transcript correction, better diarization fallback, and a small review dashboard.
