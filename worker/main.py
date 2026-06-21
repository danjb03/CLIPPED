"""Clip Engine — FastAPI worker.

Routes: /health, /ingest, /transcribe, /select, /render, /copy, /export.
"""

import subprocess

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import clipselect as select_mod
import copygen as copy_mod
import exporter as export_mod
import ingest as ingest_mod
import render as render_mod
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


class IngestRequest(BaseModel):
    url: str


class JobRequest(BaseModel):
    job_id: str


class SelectRequest(BaseModel):
    job_id: str
    count: int = 3


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
def select(req: SelectRequest):
    if req.count < 1:
        raise HTTPException(status_code=400, detail="count must be >= 1")
    try:
        path = select_mod.select(req.job_id, req.count)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"job_id": req.job_id, "clips": path}


@app.post("/render")
def render(req: JobRequest):
    try:
        outputs = render_mod.render(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "renders": outputs}


@app.post("/copy")
def copy(req: JobRequest):
    try:
        path = copy_mod.generate_copy(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "clips": path}


@app.post("/export")
def export(req: JobRequest):
    try:
        path = export_mod.export(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"job_id": req.job_id, "export": path}
