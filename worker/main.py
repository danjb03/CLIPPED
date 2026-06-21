"""Clip Engine — FastAPI worker.

Implemented: /health, /ingest, /transcribe (Phase 1). The remaining routes are
honest stubs filled in during their phase.
"""

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ingest as ingest_mod
import transcribe as transcribe_mod
from paths import REPO_ROOT

# .env.local lives at the repo root and is shared with the web app.
load_dotenv(REPO_ROOT / ".env.local")

app = FastAPI(title="Clip Engine Worker", version="0.0.0")

# Local dev only: the Next.js UI (localhost:3000) calls this worker directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


# --- Stubs for later phases (declared now so the API shape is stable) ---


class IngestRequest(BaseModel):
    url: str


class JobRequest(BaseModel):
    job_id: str


class SelectRequest(BaseModel):
    job_id: str
    count: int = 3


def _not_implemented(phase: str):
    raise HTTPException(status_code=501, detail=f"Not implemented yet — {phase}.")


@app.post("/ingest")
def ingest(req: IngestRequest):
    try:
        job_id = ingest_mod.download(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"job_id": job_id}


@app.post("/transcribe")
def transcribe(req: JobRequest):
    try:
        path = transcribe_mod.transcribe(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "transcript": path}


@app.post("/select")
def select(_: SelectRequest):
    _not_implemented("Phase 2: Claude clip selection")


@app.post("/render")
def render(_: JobRequest):
    _not_implemented("Phase 3: ffmpeg + Remotion render")


@app.post("/copy")
def copy(_: JobRequest):
    _not_implemented("Phase 6: Claude copy generation")
