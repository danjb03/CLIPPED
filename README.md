# Clip Engine

Turn one long video (link) into N vertical, captioned, ready-to-post clips — with
optional two-speaker split-screen — plus AI-written post copy. **Local, single-user,
no cloud, no database, no auth.**

This repo is being built phase-by-phase per the PRD. **Current status: Phase 0 — Scaffold.**

## Stack

| Layer | Choice |
|---|---|
| Control UI + caption render | Next.js 14 (App Router, TS) + Remotion |
| Heavy lifting (download, ffmpeg, face detect) | Python 3.11 FastAPI worker |
| Download | yt-dlp |
| Transcribe + diarise | AssemblyAI (word-level timestamps + speaker labels) |
| Clip select + post copy | Anthropic API (Claude) |
| Cut / crop / stack | ffmpeg |
| Storage | local filesystem — `output/<job_id>/` |

## Layout

```
.
├─ web/        # Next.js 14 + Remotion control UI
├─ worker/     # Python FastAPI worker (the heavy lifting)
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
ANTHROPIC_API_KEY=...
ASSEMBLYAI_API_KEY=...
```

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

## Phase 0 acceptance test

1. `npm run dev` in `web/` serves the "Clip Engine" page at http://localhost:3000.
2. `GET localhost:8000/health` returns `{"ok": true}`.

## Roadmap

- **Phase 0 — Scaffold** ✅ (this commit)
- Phase 1 — Ingest + transcribe (yt-dlp + AssemblyAI)
- Phase 2 — Clip selection (Claude)
- Phase 3 — Vertical captioned render (Remotion + ffmpeg)
- Phase 4 — Split-screen mode (static face stack)
- Phase 5 — Local control UI
- Phase 6 — Copy generation + export

Phases 0 → 1 → 2 → 3 → 6 give a finished, usable tool with none of the hard ML.
