# Clip Engine

Turn one long video (link) into N vertical, captioned, ready-to-post clips — with
optional two-speaker split-screen — plus AI-written post copy. **Local, single-user,
no cloud, no database, no auth.**

This repo is being built phase-by-phase per the PRD. **Current status: Phase 1 — Ingest + transcribe.**

## Stack

| Layer | Choice |
|---|---|
| Control UI + caption render | Next.js 14 (App Router, TS) + Remotion |
| Heavy lifting (download, ffmpeg, face detect) | Python 3.11 FastAPI worker |
| Download | yt-dlp |
| Transcribe | faster-whisper (local, free) — word-level timestamps |
| Diarise (speaker labels) | pyannote.audio (local) — needs a free Hugging Face token |
| Clip select + post copy | Anthropic API (Claude) |
| Cut / crop / stack | ffmpeg |
| Storage | local filesystem — `output/<job_id>/` |

## Layout

```
.
├─ web/        # Next.js 14 + Remotion control UI
├─ worker/     # Python FastAPI worker (the heavy lifting)
│  ├─ main.py       # API routes
│  ├─ paths.py      # output/<job_id>/ filesystem helpers
│  ├─ ingest.py     # yt-dlp download
│  ├─ transcribe.py # faster-whisper + pyannote -> transcript.json
│  ├─ select.py / copygen.py / split.py  # later phases (copygen, not "copy",
│  │                                       to avoid shadowing stdlib copy)
│  └─ tests/        # unit tests for the speaker-alignment logic
└─ output/     # generated artifacts, one folder per job (git-ignored)
```

## Prerequisites

On your PATH:

- Node 20+
- Python 3.11
- `ffmpeg`
- `yt-dlp` (needed from Phase 1)

## Environment

Copy the example file and fill in your keys:

```bash
cp .env.local.example .env.local
```

```
ANTHROPIC_API_KEY=...      # clip selection + copy (Phases 2/6)
HUGGINGFACE_TOKEN=...       # diarisation (pyannote). Optional but needed for speaker labels.
```

Transcription is local (faster-whisper) — no key. Diarisation uses pyannote, which
needs a free Hugging Face token **and** you must accept the model terms once at
<https://hf.co/pyannote/speaker-diarization-3.1>. Without it, transcription still
runs but every word is labelled speaker `A`.

`.env.local` is git-ignored and read by **both** services.

## Run

### Worker (FastAPI)

```bash
cd worker
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Health check:

```bash
curl localhost:8000/health
# {"ok": true}
```

### Web (Next.js)

```bash
cd web
npm install
npm run dev
# http://localhost:3000
```

## Phase 1 usage

```bash
# 1. download a video
curl -s -XPOST localhost:8000/ingest -H 'content-type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=..."}'
# -> {"job_id":"abc123..."}   (saved to output/<job_id>/source.mp4)

# 2. transcribe + diarise
curl -s -XPOST localhost:8000/transcribe -H 'content-type: application/json' \
  -d '{"job_id":"abc123..."}'
# -> writes output/<job_id>/transcript.json = [{word, start, end, speaker}]
```

The first `/transcribe` downloads the Whisper model (set size via `WHISPER_MODEL`).

## Tests

```bash
cd worker && python tests/test_transcribe.py   # speaker-alignment logic (no models)
```

## Acceptance tests

- **Phase 0:** `npm run dev` serves the "Clip Engine" page; `GET /health` → `{"ok": true}`.
- **Phase 1:** given a real 2-person podcast URL, `transcript.json` exists, has
  word-level timestamps, and ≥2 distinct speaker labels. (Requires `yt-dlp` on
  PATH and a Hugging Face token for diarisation.)

## Roadmap

- **Phase 0 — Scaffold** ✅
- **Phase 1 — Ingest + transcribe** ✅ (yt-dlp + faster-whisper + pyannote)
- Phase 2 — Clip selection (Claude)
- Phase 3 — Vertical captioned render (Remotion + ffmpeg)
- Phase 4 — Split-screen mode (static face stack)
- Phase 5 — Local control UI
- Phase 6 — Copy generation + export

Phases 0 → 1 → 2 → 3 → 6 give a finished, usable tool with none of the hard ML.
