"""Phase 6 — export.

POST /export {job_id} zips renders/*.mp4 plus a captions.txt (all per-clip copy)
into output/<job_id>/export.zip.
"""

import json
import zipfile
from typing import Any, Dict, List

from paths import clips_path, job_dir


def build_captions_txt(clips: List[Dict[str, Any]]) -> str:
    """One block per clip: header, hook, and the generated copy."""
    blocks: List[str] = []
    for i, c in enumerate(clips):
        start, end = float(c.get("start", 0.0)), float(c.get("end", 0.0))
        lines = [f"=== clip_{i}.mp4  ({start:.1f}-{end:.1f}s) ==="]
        if c.get("hook"):
            lines.append(f"Hook: {c['hook']}")
        lines.append("")
        lines.append(c.get("copy") or "(no copy generated)")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def export_carousels(job_id: str) -> str:
    """Zip only the carousel slide PNGs (+ carousels.txt) into carousels.zip."""
    jd = job_dir(job_id)
    carousels_dir = jd / "carousels"
    pngs = sorted(carousels_dir.rglob("*.png")) if carousels_dir.exists() else []
    if not pngs:
        raise FileNotFoundError(f"no carousel slides found for job {job_id}")

    zip_path = jd / "carousels.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for png in pngs:
            z.write(png, arcname=str(png.relative_to(carousels_dir)))
        txt = jd / "carousels.txt"
        if txt.exists():
            z.write(txt, arcname="carousels.txt")
    return str(zip_path)


def export(job_id: str) -> str:
    """Zip renders/*.mp4 + captions.txt into export.zip; return its path."""
    jd = job_dir(job_id)
    renders_dir = jd / "renders"
    cpath = clips_path(job_id)
    if not renders_dir.exists() or not any(renders_dir.glob("*.mp4")):
        raise FileNotFoundError(f"no renders found for job {job_id}")

    clips = json.loads(cpath.read_text()) if cpath.exists() else []
    zip_path = jd / "export.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for mp4 in sorted(renders_dir.glob("*.mp4")):
            z.write(mp4, arcname=f"renders/{mp4.name}")
        z.writestr("captions.txt", build_captions_txt(clips))
        # carousels are optional (separate text artifact)
        for extra in ("carousels.txt", "carousels.json"):
            p = jd / extra
            if p.exists():
                z.write(p, arcname=extra)
        # rendered carousel slide images, if any
        carousels_dir = jd / "carousels"
        if carousels_dir.exists():
            for png in sorted(carousels_dir.rglob("*.png")):
                z.write(png, arcname=f"carousels/{png.relative_to(carousels_dir)}")

    return str(zip_path)
