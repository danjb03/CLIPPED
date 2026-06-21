"""Clip Engine — FastAPI worker.

Routes: /health, /ingest, /transcribe, /select, /render, /copy, /export.
"""

import subprocess

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import carousel as carousel_mod
import clipselect as select_mod
import copygen as copy_mod
import exporter as export_mod
import ingest as ingest_mod
import render as render_mod
import transcribe as transcribe_mod
from paths import OUTPUT_DIR, REPO_ROOT

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


# Serve generated artifacts (rendered clips, slides, zips) for the UI to preview.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")


class IngestRequest(BaseModel):
    url: str


class JobRequest(BaseModel):
    job_id: str


class SelectRequest(BaseModel):
    job_id: str
    count: int = 3


class RenderOneRequest(BaseModel):
    job_id: str
    index: int
    style: dict | None = None


class RegenerateRequest(BaseModel):
    job_id: str
    index: int


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


@app.post("/render/one")
def render_one(req: RenderOneRequest):
    try:
        path = render_mod.render_one(req.job_id, req.index, req.style)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except IndexError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "index": req.index, "render": path}


@app.post("/select/regenerate")
def select_regenerate(req: RegenerateRequest):
    try:
        clip = select_mod.regenerate_one(req.job_id, req.index)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except IndexError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "index": req.index, "clip": clip}


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


@app.post("/carousels")
def carousels(req: JobRequest):
    try:
        path = carousel_mod.generate(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "carousels": path}


@app.post("/carousels/render")
def render_carousels(req: JobRequest):
    try:
        outputs = render_mod.render_carousels(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "slides": outputs}


@app.post("/export")
def export(req: JobRequest):
    try:
        path = export_mod.export(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"job_id": req.job_id, "export": path}
