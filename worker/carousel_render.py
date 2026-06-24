"""Carousel image rendering — split-screen PNG slides.

A carousel slide here is what the creator's "Split Screen Carousel Storyline"
prompt actually targets: two video frames stacked vertically, each with one
sentence of caption overlaid in the lower portion.

For each carousel slide produced by carousel.py:
  - Split the slide's two sentences.
  - Find each sentence's start timestamp in the transcript (token match).
  - Extract a still frame from source.mp4 at each timestamp.
  - vstack the two frames (1080x960 each) into one 1080x1920 PNG.
  - Burn the sentence text on the lower portion of each panel.

Output: output/<job_id>/carousels/carousel_<n>/slide_<i>.png
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from paths import job_dir, source_path, transcript_path

W, H = 1080, 1920
PANEL_W, PANEL_H = 1080, 960
PANEL_ASPECT = PANEL_W / PANEL_H  # 1.125

# Captions are rendered via libass (the same engine clip captions use), not
# drawtext — better anti-aliasing/wrap and the filter is universally available.
FONT_NAME = "DejaVu Sans"
CAPTION_Y_FRAC = 0.78  # caption baseline as fraction of panel height


# --- Pure, testable helpers (no ffmpeg) ---


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def split_sentences(slide_text: str) -> List[str]:
    """Split a slide like 'Sentence one. Sentence two.' into two sentences.
    Pads to exactly 2 if there's only one; truncates extras."""
    parts = re.split(r"(?<=[.!?])\s+", slide_text.strip())
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return ["", ""]
    while len(parts) < 2:
        parts.append(parts[-1])
    return parts[:2]


def find_sentence_time(sentence: str, transcript: List[Dict[str, Any]]) -> float:
    """Return the start timestamp where `sentence` best matches in `transcript`."""
    sent_tokens = _normalize(sentence).split()
    if not sent_tokens or not transcript:
        return 0.0
    flat = [_normalize(str(w["word"])).strip() for w in transcript]
    n = min(5, len(sent_tokens))
    needle = sent_tokens[:n]
    # exact contiguous match on the first n tokens
    for i in range(len(flat) - n + 1):
        if all(flat[i + j] == needle[j] for j in range(n)):
            return float(transcript[i]["start"])
    # fallback: best partial match by token overlap in the window
    best_score, best_idx = -1, 0
    for i in range(len(flat) - n + 1):
        score = sum(1 for j in range(n) if flat[i + j] == needle[j])
        if score > best_score:
            best_score, best_idx = score, i
    return float(transcript[best_idx]["start"])


def wrap(text: str, max_chars: int = 36) -> str:
    """Naive word-wrap so long sentences break onto a second line."""
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


# --- ffmpeg orchestration ---


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_panel_ass(text: str) -> str:
    """Single-event ASS that holds `text` on screen for the whole panel duration."""
    margin_v = max(10, round((1 - CAPTION_Y_FRAC) * PANEL_H))
    text = _ass_escape(text).replace("\n", "\\N")
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {PANEL_W}\n"
        f"PlayResY: {PANEL_H}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{FONT_NAME},54,&H00FFFFFF,&H00FFFFFF,&H00000000,"
        f"&H64000000,-1,0,0,0,100,100,0,0,1,3,2,2,60,60,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
        f"Dialogue: 0,0:00:00.00,9:59:59.99,Cap,,0,0,0,,{text}\n"
    )


def _subtitles_filter(ass_path: Path) -> str:
    p = str(ass_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles='{p}'"


def build_slide(
    src: Path,
    t_top: float,
    t_bottom: float,
    text_top: str,
    text_bottom: str,
    out: Path,
) -> None:
    """Render one carousel PNG: top frame (with text) over bottom frame (with text)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    top_ass = out.parent / f".top_{out.stem}.ass"
    bot_ass = out.parent / f".bot_{out.stem}.ass"
    top_ass.write_text(build_panel_ass(text_top))
    bot_ass.write_text(build_panel_ass(text_bottom))
    try:
        crop = (
            f"crop=min(iw\\,ih*{PANEL_ASPECT}):min(ih\\,iw/{PANEL_ASPECT}),"
            f"scale={PANEL_W}:{PANEL_H},setsar=1"
        )
        fc = (
            f"[0:v]{crop},{_subtitles_filter(top_ass)}[t];"
            f"[1:v]{crop},{_subtitles_filter(bot_ass)}[b];"
            f"[t][b]vstack=inputs=2[v]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{max(0.0, t_top):.3f}", "-i", str(src),
            "-ss", f"{max(0.0, t_bottom):.3f}", "-i", str(src),
            "-filter_complex", fc,
            "-map", "[v]", "-frames:v", "1", str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    finally:
        for f in (top_ass, bot_ass):
            if f.exists():
                f.unlink()


def render_split_carousels(job_id: str) -> List[str]:
    """Render every carousel slide as a 1080x1920 split-screen PNG."""
    src = source_path(job_id)
    if not src.exists():
        raise FileNotFoundError(f"source.mp4 not found for job {job_id}")
    cjson = job_dir(job_id) / "carousels.json"
    if not cjson.exists():
        raise FileNotFoundError(f"carousels.json not found for job {job_id}")
    transcript = json.loads(transcript_path(job_id).read_text())
    carousels = json.loads(cjson.read_text())

    base = job_dir(job_id) / "carousels"
    outputs: List[str] = []
    for c in carousels:
        n = c.get("number", len(outputs) + 1)
        slides = c.get("slides", [])
        cdir = base / f"carousel_{n}"
        cdir.mkdir(parents=True, exist_ok=True)
        for i, slide_text in enumerate(slides, start=1):
            top_text, bot_text = split_sentences(slide_text)
            t_top = find_sentence_time(top_text, transcript)
            t_bot = find_sentence_time(bot_text, transcript)
            out = cdir / f"slide_{i}.png"
            build_slide(src, t_top, t_bot, top_text, bot_text, out)
            outputs.append(str(out))
    return outputs
