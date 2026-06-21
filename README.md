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
│  ├─ clipselect.py # Claude clip selection -> clips.json
│  ├─ render.py     # ffmpeg crop + Remotion caption render -> renders/*.mp4
│  ├─ copygen.py    # Claude per-clip post copy -> clips.json
│  ├─ carousel.py   # Claude carousel storylines -> carousels.json + .txt
│  ├─ exporter.py   # zip renders/*.mp4 + captions.txt (+ carousels) -> export.zip
│  ├─ split.py      # Phase 4 (split-screen). clipselect/copygen are renamed
│  │                  from select/copy to avoid shadowing stdlib modules.
│  └─ tests/        # unit tests (alignment, selection, render, export)
├─ web/
│  ├─ app/         # control UI (page, ClipCard) + styles
│  ├─ lib/api.ts   # typed worker client
│  └─ remotion/    # Captions + CarouselSlide compositions
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

## Control UI (Phase 5)

With both services running, drive the whole pipeline from http://localhost:3000:

1. Paste a video URL, set **Posts (N)**, optionally toggle split-screen, click
   **Analyse & generate** — runs ingest → transcribe → select → render → copy.
2. Each clip shows a **preview**, the hook, editable **copy** (copy-to-clipboard),
   and **Style** controls (text/highlight colour, size, caption X/Y) with
   **Apply style & re-render**, plus **Regenerate clip** (re-picks a fresh,
   non-overlapping moment and re-renders just that slot).
3. **Generate carousels** renders the carousel slides inline; **Export .zip**
   bundles everything and gives a download link.

The worker serves rendered artifacts to the UI from `GET /files/<job_id>/...`.
Split-screen is a present-but-fallback toggle until Phase 4 lands (it currently
produces a single centre crop).

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

## Phase 2 usage

```bash
# pick the N best clips (needs ANTHROPIC_API_KEY)
curl -s -XPOST localhost:8000/select -H 'content-type: application/json' \
  -d '{"job_id":"abc123...","count":3}'
# -> writes output/<job_id>/clips.json =
#    [{start, end, hook, reason, speaker_focus: "A|B|both"}]
```

Claude reads the timestamped transcript and returns strict JSON (one retry on a
parse failure). Each start is snapped to a real word boundary, clamped inside the
video duration, and nudged to 15-60s. Model via `ANTHROPIC_MODEL` (default
`claude-sonnet-4-6`). The selection prompt in `clipselect.py` is a generic
placeholder — swap in your own.

## Phase 3 usage

```bash
# render every clip in clips.json to a 9:16 captioned mp4
curl -s -XPOST localhost:8000/render -H 'content-type: application/json' \
  -d '{"job_id":"abc123..."}'
# -> output/<job_id>/renders/clip_0.mp4, clip_1.mp4, ...
```

For each clip the worker (1) trims `source.mp4` to `[start, end]` and centre-crops
/ scales to **1080×1920**, (2) slices the segment's words and re-bases them to
clip-relative time, (3) drives the Remotion `Captions` composition to burn
word-synced captions. The cropped clip is staged under `web/public/clips/` (so
`staticFile()` can load it) and removed afterwards. Requires `web/` deps installed
(`npm install`) and `ffmpeg` on PATH.

Caption style (defaults baked in: bold white, dark stroke, centred lower-third,
yellow active-word highlight) is a `style` object — `fontFamily, fontSize, color,
strokeColor, strokeWidth, highlightColor, maxWidth, position{x,y}` (x/y as 0..1
fractions). Defaults live in `worker/render.py` and `web/remotion/types.ts`.

## Phase 6 usage

```bash
# generate post copy per clip (needs ANTHROPIC_API_KEY)
curl -s -XPOST localhost:8000/copy -H 'content-type: application/json' \
  -d '{"job_id":"abc123..."}'
# -> adds a "copy" field to each clip in clips.json

# bundle everything for posting
curl -s -XPOST localhost:8000/export -H 'content-type: application/json' \
  -d '{"job_id":"abc123..."}'
# -> output/<job_id>/export.zip  (renders/clip_N.mp4 + captions.txt)
```

The copy prompt in `copygen.py` is a generic placeholder — swap in your own.

### Carousels (text storylines)

A separate text artifact from the video clips: reads the whole transcript and
extracts 6-10 carousel storylines (internal title + 4 story-arc slides) using the
creator's prompt in `carousel.py`.

```bash
curl -s -XPOST localhost:8000/carousels -H 'content-type: application/json' \
  -d '{"job_id":"abc123..."}'
# -> output/<job_id>/carousels.json (structured) + carousels.txt (postable)
```

Render the carousels as post-ready image slides (1080×1350 PNGs):

```bash
curl -s -XPOST localhost:8000/carousels/render -H 'content-type: application/json' \
  -d '{"job_id":"abc123..."}'
# -> output/<job_id>/carousels/carousel_<n>/slide_<i>.png
```

`carousels.txt` / `carousels.json` and the rendered slide PNGs are added to
`export.zip` when present. Note: speaker labels in the transcript are `A`/`B`, not
real names, so the model can't reliably attribute lines to "Neil" specifically.

## Tests

```bash
cd worker
python tests/test_transcribe.py   # speaker-alignment logic (no models)
python tests/test_select.py       # clip selection: snapping, validation, JSON
python tests/test_render.py       # render helpers: word-slicing, ffmpeg cmd
python tests/test_export.py       # copy attach (stubbed Claude) + export zip
python tests/test_carousel.py     # carousel parsing + generate + export
```

## Acceptance tests

- **Phase 0:** `npm run dev` serves the "Clip Engine" page; `GET /health` → `{"ok": true}`.
- **Phase 1:** given a real 2-person podcast URL, `transcript.json` exists, has
  word-level timestamps, and ≥2 distinct speaker labels. (Requires `yt-dlp` on
  PATH and a Hugging Face token for diarisation.)
- **Phase 2:** `clips.json` has exactly `count` segments, each within the video
  duration, each starting on a word boundary, valid JSON. (Requires
  `ANTHROPIC_API_KEY`.)
- **Phase 3:** rendering a segment produces a 1080×1920 mp4 with readable captions
  in sync with speech for the full clip.
- **Phase 6:** `export.zip` contains every rendered clip and a `captions.txt` with
  matching copy per clip. (Copy generation requires `ANTHROPIC_API_KEY`.)

## Roadmap

- **Phase 0 — Scaffold** ✅
- **Phase 1 — Ingest + transcribe** ✅ (yt-dlp + faster-whisper + pyannote)
- **Phase 2 — Clip selection** ✅ (Claude)
- **Phase 3 — Vertical captioned render** ✅ (Remotion + ffmpeg)
- **Phase 6 — Copy generation + export** ✅ (Claude + zip)
- **Phase 5 — Local control UI** ✅ (drive everything from one screen)
- Plus: carousel storylines + rendered carousel slides (creator's prompt)
- Phase 4 — Split-screen mode (static face stack) — the remaining upgrade

Phases 0 → 1 → 2 → 3 → 5 → 6 are done: a finished, usable tool with a UI.
Phase 4 (split-screen) is the last upgrade; the UI already has the toggle.
