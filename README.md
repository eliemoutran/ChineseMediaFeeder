# ChineseMediaFeeder

V1 generates three MP4 variants from local Mandarin episode files:

- Mode 1: no subtitles
- Mode 2: pinyin subtitles
- Mode 3: alternating pinyin and English subtitles

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

Transcription runs two OpenAI passes:

- `whisper-1` writes the timing transcript used for subtitle cue start/end times.
- `OPENAI_TRANSCRIBE_MODEL` adds diarized speaker context. Its text/timing is saved for QA, but it does not override the timing transcript.

## Commands

```bash
cmf scan
cmf process media/input/episode-001.mp4
cmf process-all
cmf status
```
