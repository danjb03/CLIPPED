"""Clip Engine — FastAPI worker.

Phase 0 (scaffold): only `/health` is implemented. The remaining routes are
declared as honest stubs so the API surface and repo structure match the PRD;
each is filled in during its phase.
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# .env.local lives at the repo root and is shared with the web app.
REPO_ROOT = Path(__file__).resolve().parent.parent
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
def ingest(_: IngestRequest):
    _not_implemented("Phase 1: yt-dlp download")


@app.post("/transcribe")
def transcribe(_: JobRequest):
    _not_implemented("Phase 1: AssemblyAI transcription")


@app.post("/select")
def select(_: SelectRequest):
    _not_implemented("Phase 2: Claude clip selection")


@app.post("/render")
def render(_: JobRequest):
    _not_implemented("Phase 3: ffmpeg + Remotion render")


@app.post("/copy")
def copy(_: JobRequest):
    _not_implemented("Phase 6: Claude copy generation")
