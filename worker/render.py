"""Phase 3 — vertical captioned render.

For each clip in clips.json:
  1. ffmpeg trims source.mp4 to [start, end] and centre-crops/scales to 1080x1920.
  2. The segment's words are sliced out of transcript.json and re-based to
     clip-relative time (so caption sync starts at 0).
  3. Remotion burns word-synced captions over the cropped clip -> renders/clip_N.mp4.

The cropped base clip is staged under web/public/clips/ so Remotion's staticFile()
can load it during render, then removed afterwards.
"""

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List

from paths import REPO_ROOT, clips_path, job_dir, source_path, transcript_path

WEB_DIR = REPO_ROOT / "web"
PUBLIC_CLIPS = WEB_DIR / "public" / "clips"
FPS = int(os.environ.get("RENDER_FPS", "30"))

# Largest centred 9:16 rectangle that fits the source, scaled to 1080x1920.
CROP_FILTER = r"crop=min(iw\,ih*9/16):min(ih\,iw*16/9),scale=1080:1920,setsar=1"

DEFAULT_STYLE: Dict[str, Any] = {
    "fontFamily": "Inter, Arial, sans-serif",
    "fontSize": 84,
    "color": "#ffffff",
    "strokeColor": "#000000",
    "strokeWidth": 10,
    "highlightColor": "#ffe600",
    "maxWidth": 0.9,
    "position": {"x": 0.5, "y": 0.78},
}

DEFAULT_CAROUSEL_STYLE: Dict[str, Any] = {
    "background": "#111317",
    "color": "#ffffff",
    "accent": "#ffe600",
    "fontFamily": "Inter, Arial, sans-serif",
}


# --- Pure, testable helpers (no ffmpeg, no Remotion) ---


def slice_words(
    words: List[Dict[str, Any]], start: float, end: float
) -> List[Dict[str, Any]]:
    """Return words overlapping [start, end], re-based to clip-relative time."""
    out: List[Dict[str, Any]] = []
    for w in words:
        ws, we = float(w["start"]), float(w["end"])
        if we <= start or ws >= end:
            continue
        out.append(
            {
                "word": w["word"],
                "start": round(max(0.0, ws - start), 3),
                "end": round(max(0.0, we - start), 3),
                "speaker": w.get("speaker", "A"),
            }
        )
    return out


def build_ffmpeg_cmd(src: str, start: float, duration: float, out: str) -> List[str]:
    return [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-vf", CROP_FILTER,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(out),
    ]


def build_props(
    video_src: str, words: List[Dict[str, Any]], duration: float, style: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "videoSrc": video_src,
        "words": words,
        "style": style,
        "fps": FPS,
        "durationInSeconds": round(duration, 3),
    }


def build_carousel_props(
    text: str, index: int, total: int, style: Dict[str, Any]
) -> Dict[str, Any]:
    return {"text": text, "index": index, "total": total, **style}


# --- ffmpeg + Remotion orchestration ---


def _crop_clip(src, start: float, duration: float, out) -> None:
    subprocess.run(
        build_ffmpeg_cmd(str(src), start, duration, str(out)),
        check=True, capture_output=True, text=True,
    )


def _remotion_render(props_file, out) -> None:
    cmd = [
        "npx", "remotion", "render",
        "remotion/index.ts", "Captions",
        str(out),
        f"--props={props_file}",
        "--log=error",
    ]
    subprocess.run(cmd, check=True, cwd=str(WEB_DIR), capture_output=True, text=True)


def _remotion_still(props_file, out) -> None:
    cmd = [
        "npx", "remotion", "still",
        "remotion/index.ts", "CarouselSlide",
        str(out),
        f"--props={props_file}",
        "--log=error",
    ]
    subprocess.run(cmd, check=True, cwd=str(WEB_DIR), capture_output=True, text=True)


def _load_job(job_id: str):
    src = source_path(job_id)
    if not src.exists():
        raise FileNotFoundError(f"source.mp4 not found for job {job_id}")
    cpath, tpath = clips_path(job_id), transcript_path(job_id)
    if not cpath.exists():
        raise FileNotFoundError(f"clips.json not found for job {job_id}")
    if not tpath.exists():
        raise FileNotFoundError(f"transcript.json not found for job {job_id}")
    return src, json.loads(cpath.read_text()), json.loads(tpath.read_text())


def _render_one(job_id, idx, clip, words, style, src) -> str:
    start, end = float(clip["start"]), float(clip["end"])
    duration = max(0.1, end - start)

    renders_dir = job_dir(job_id) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    PUBLIC_CLIPS.mkdir(parents=True, exist_ok=True)

    base_name = f"{job_id}_{idx}.mp4"
    base_path = PUBLIC_CLIPS / base_name
    out_path = renders_dir / f"clip_{idx}.mp4"
    props_file = renders_dir / f".props_{idx}.json"
    try:
        _crop_clip(src, start, duration, base_path)
        clip_words = slice_words(words, start, end)
        props = build_props(f"clips/{base_name}", clip_words, duration, style)
        props_file.write_text(json.dumps(props))
        _remotion_render(props_file, out_path)
    finally:
        for tmp in (base_path, props_file):
            if tmp.exists():
                tmp.unlink()
    return str(out_path)


def render(job_id: str, style: Dict[str, Any] | None = None) -> List[str]:
    """Render every clip in clips.json to renders/clip_N.mp4; return their paths."""
    src, clips, words = _load_job(job_id)
    style = {**DEFAULT_STYLE, **(style or {})}
    return [
        _render_one(job_id, idx, clip, words, style, src)
        for idx, clip in enumerate(clips)
    ]


def render_one(job_id: str, index: int, style: Dict[str, Any] | None = None) -> str:
    """Re-render a single clip (e.g. after a style change). Returns its path."""
    src, clips, words = _load_job(job_id)
    if index < 0 or index >= len(clips):
        raise IndexError(f"clip index {index} out of range (have {len(clips)})")
    style = {**DEFAULT_STYLE, **(style or {})}
    return _render_one(job_id, index, clips[index], words, style, src)


def render_carousels(job_id: str, style: Dict[str, Any] | None = None) -> List[str]:
    """Render each carousel slide to a PNG under output/<job_id>/carousels/."""
    cjson = job_dir(job_id) / "carousels.json"
    if not cjson.exists():
        raise FileNotFoundError(f"carousels.json not found for job {job_id}")

    carousels = json.loads(cjson.read_text())
    style = {**DEFAULT_CAROUSEL_STYLE, **(style or {})}
    base_out = job_dir(job_id) / "carousels"
    base_out.mkdir(parents=True, exist_ok=True)

    outputs: List[str] = []
    for c in carousels:
        number = c.get("number", len(outputs) + 1)
        slides = c.get("slides", [])
        cdir = base_out / f"carousel_{number}"
        cdir.mkdir(parents=True, exist_ok=True)
        for i, text in enumerate(slides, start=1):
            out_png = cdir / f"slide_{i}.png"
            props_file = cdir / f".props_{i}.json"
            try:
                props = build_carousel_props(text, i, len(slides), style)
                props_file.write_text(json.dumps(props))
                _remotion_still(props_file, out_png)
                outputs.append(str(out_png))
            finally:
                if props_file.exists():
                    props_file.unlink()

    return outputs
