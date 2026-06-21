"""Phase 6 — per-clip post copy with Claude.

POST /copy {job_id} reads clips.json + transcript.json, and for each clip asks
Claude to write a short social caption from that segment's transcript, attaching
it to the clip as `copy`. Result is written back to clips.json.

NOTE: named copygen.py (not copy.py) because a module named `copy` on the
worker's sys.path shadows Python's stdlib `copy`, which FastAPI imports.

TODO: replace SYSTEM_PROMPT / build_copy_prompt with the user's own copy prompt
when provided. Until then this is a generic caption writer.
"""

import json
import os
from typing import Any, Dict, List

from paths import clips_path, transcript_path

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# --- PLACEHOLDER PROMPT (swap in the user's prompt here) ---
SYSTEM_PROMPT = (
    "You write punchy, scroll-stopping social captions for short vertical video "
    "clips (TikTok / Reels / Shorts). You write in the creator's voice, lead with "
    "the hook, keep it tight (1-2 sentences), and add 3-5 relevant hashtags on a "
    "new line. No emojis unless they earn their place, no hashtag soup."
)


def build_copy_prompt(segment_text: str, hook: str) -> str:
    return (
        f"Hook for this clip: {hook or '(none provided)'}\n\n"
        f"Clip transcript:\n{segment_text}\n\n"
        f"Write the post caption for this clip. Return ONLY the caption text "
        f"(caption then hashtags on a new line) — no preamble, no quotes."
    )


# --- Pure, testable helpers (no API, no IO) ---


def segment_text(words: List[Dict[str, Any]], start: float, end: float) -> str:
    """Plain transcript text for the words overlapping [start, end]."""
    parts = [
        str(w["word"])
        for w in words
        if not (float(w["end"]) <= start or float(w["start"]) >= end)
    ]
    return " ".join(parts).strip()


# --- API + IO ---


def _ask_claude(seg_text: str, hook: str) -> str:
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_copy_prompt(seg_text, hook)}],
    )
    return "".join(
        b.text for b in resp.content if getattr(b, "type", "") == "text"
    ).strip()


def generate_copy(job_id: str) -> str:
    """Generate post copy per clip, attach to clips.json, return its path."""
    cpath, tpath = clips_path(job_id), transcript_path(job_id)
    if not cpath.exists():
        raise FileNotFoundError(f"clips.json not found for job {job_id}")
    if not tpath.exists():
        raise FileNotFoundError(f"transcript.json not found for job {job_id}")

    clips = json.loads(cpath.read_text())
    words = json.loads(tpath.read_text())

    for clip in clips:
        seg = segment_text(words, float(clip["start"]), float(clip["end"]))
        clip["copy"] = _ask_claude(seg, clip.get("hook", ""))

    cpath.write_text(json.dumps(clips, ensure_ascii=False, indent=2))
    return str(cpath)
