"""Clip Engine — FastAPI worker.

Routes: /health, /ingest, /transcribe, /select, /render, /copy, /export.
"""

import os as _os
import subprocess

import uuid

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import carousel as carousel_mod
import clipselect as select_mod
import copygen as copy_mod
import exporter as export_mod
import ingest as ingest_mod
import jobs as jobs_mod
import render as render_mod
import transcribe as transcribe_mod
from paths import OUTPUT_DIR, REPO_ROOT, job_dir, source_path

# .env.local lives at the repo root and is shared with the web app.
load_dotenv(REPO_ROOT / ".env.local")

# Optional shared secret. When WORKER_TOKEN is set (recommended for a hosted,
# internet-facing worker), mutating endpoints require a matching X-Worker-Token
# header so strangers can't spend your API budget. /health and /files stay open.
WORKER_TOKEN = _os.environ.get("WORKER_TOKEN")


def require_token(x_worker_token: str | None = Header(default=None)):
    if WORKER_TOKEN and x_worker_token != WORKER_TOKEN:
        raise HTTPException(status_code=401, detail="invalid or missing worker token")


app = FastAPI(title="Clip Engine Worker", version="0.0.0")

# CORS: the UI (localhost or a Vercel domain) calls this worker directly. Set
# CORS_ORIGINS to a comma-separated allowlist; defaults to "*" since this is a
# single-user tool with no credentials/cookies.
_origins = [o.strip() for o in _os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
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


class RenderRequest(BaseModel):
    job_id: str
    mode: str = "single"  # "single" | "split"


class RenderOneRequest(BaseModel):
    job_id: str
    index: int
    style: dict | None = None
    mode: str = "single"


class RegenerateRequest(BaseModel):
    job_id: str
    index: int


class CarouselRequest(BaseModel):
    job_id: str
    creator: str | None = None  # speaker label of the creator (-> "Neil")


class RunRequest(BaseModel):
    url: str | None = None         # paste-link path; ignored if job_id given
    job_id: str | None = None      # use an existing source (e.g. just uploaded)
    count: int = 3
    mode: str = "single"           # "single" | "split"


def _pipeline_steps(req: RunRequest):
    """Build the (label, fn) sequence the background runner walks."""

    def do_download(j):
        if req.job_id:
            j.job_id = req.job_id
        else:
            j.job_id = ingest_mod.download(req.url or "")

    def do_transcribe(j):
        transcribe_mod.transcribe(j.job_id)

    def do_select(j):
        if req.count < 1:
            raise ValueError("count must be >= 1")
        select_mod.select(j.job_id, req.count)

    def do_render(j):
        render_mod.render(j.job_id, mode=req.mode)

    def do_copy(j):
        copy_mod.generate_copy(j.job_id)

    return [
        ("Download", do_download),
        ("Transcribe", do_transcribe),
        ("Select", do_select),
        ("Render", do_render),
        ("Copy", do_copy),
    ]


@app.post("/run", dependencies=[Depends(require_token)])
def run(req: RunRequest, bg: BackgroundTasks):
    """Start the full pipeline as a background job; return run_id immediately."""
    run_id = uuid.uuid4().hex[:12]
    jobs_mod.create(run_id, job_id=req.job_id)
    bg.add_task(jobs_mod.run_pipeline, run_id, _pipeline_steps(req))
    return {"run_id": run_id}


@app.get("/jobs/{run_id}")
def job_status(run_id: str):
    j = jobs_mod.get(run_id)
    if not j:
        raise HTTPException(status_code=404, detail="run not found")
    return j.to_dict()


@app.post("/ingest", dependencies=[Depends(require_token)])
def ingest(req: IngestRequest):
    try:
        job_id = ingest_mod.download(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"job_id": job_id}


@app.post("/upload", dependencies=[Depends(require_token)])
async def upload(file: UploadFile = File(...)):
    """Accept a directly-uploaded video file (no yt-dlp). Most reliable input —
    works regardless of YouTube/Drive blocking."""
    job_id = ingest_mod.new_job_id()
    job_dir(job_id).mkdir(parents=True, exist_ok=True)
    dest = source_path(job_id)
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"upload failed: {e}")
    finally:
        await file.close()
    if not dest.exists() or dest.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="empty upload")
    return {"job_id": job_id}


@app.post("/transcribe", dependencies=[Depends(require_token)])
def transcribe(req: JobRequest):
    try:
        path = transcribe_mod.transcribe(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "transcript": path}


@app.post("/select", dependencies=[Depends(require_token)])
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


@app.post("/render", dependencies=[Depends(require_token)])
def render(req: RenderRequest):
    try:
        outputs = render_mod.render(req.job_id, mode=req.mode)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "renders": outputs}


@app.post("/render/one", dependencies=[Depends(require_token)])
def render_one(req: RenderOneRequest):
    try:
        path = render_mod.render_one(req.job_id, req.index, req.style, req.mode)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except IndexError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "index": req.index, "render": path}


@app.post("/select/regenerate", dependencies=[Depends(require_token)])
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


@app.post("/copy", dependencies=[Depends(require_token)])
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


@app.post("/carousels", dependencies=[Depends(require_token)])
def carousels(req: CarouselRequest):
    try:
        path = carousel_mod.generate(req.job_id, req.creator)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"job_id": req.job_id, "carousels": path}


@app.post("/carousels/render", dependencies=[Depends(require_token)])
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


@app.post("/export", dependencies=[Depends(require_token)])
def export(req: JobRequest):
    try:
        path = export_mod.export(req.job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"job_id": req.job_id, "export": path}
