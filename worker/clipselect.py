"""Phase 2 — clip selection with Claude.

POST /select {job_id, count} feeds the timestamped transcript to Claude and asks
for the best N self-contained moments as strict JSON:

    [{"start", "end", "hook", "reason", "speaker_focus": "A|B|both"}]

We validate the JSON (retrying Claude once on a parse failure), snap each start to
a real word boundary, clamp inside the video duration, and nudge each segment
toward 15-60s. Result is written to output/<job_id>/clips.json.

NOTE: named clipselect.py (not select.py) — a module named `select` is shadowed
by Python's stdlib `select` (a builtin) and would be unreachable.

TODO: replace SYSTEM_PROMPT / build_user_prompt with the user's own
selection prompt when provided. Until then this is a generic selector.
"""

import json
import os
import subprocess
from typing import Any, Dict, List, Tuple

from paths import clips_path, source_path, transcript_path

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

MIN_LEN = 15.0
MAX_LEN = 60.0

# --- PLACEHOLDER PROMPT (swap in the user's prompt here) ---
SYSTEM_PROMPT = (
    "You are an expert short-form video editor. You read a podcast/interview "
    "transcript with timestamps and pick the moments that work best as standalone "
    "vertical clips: a strong hook in the first seconds, a complete thought, and a "
    "satisfying end. You never invent timestamps — you only use times present in "
    "the transcript."
)


def build_user_prompt(transcript_text: str, count: int, duration: float) -> str:
    return (
        f"Below is a transcript. Each line is `[start_seconds] SPEAKER: text`.\n"
        f"The video is {duration:.1f} seconds long.\n\n"
        f"Pick the {count} best self-contained moments to cut into vertical clips.\n"
        f"Rules:\n"
        f"- Each clip must be between {int(MIN_LEN)} and {int(MAX_LEN)} seconds.\n"
        f"- start and end are in seconds and must lie within the video duration.\n"
        f"- Start on a clean sentence boundary.\n"
        f"- speaker_focus is 'A', 'B', or 'both'.\n\n"
        f"Return ONLY a JSON array, no prose, of exactly {count} objects:\n"
        f'[{{"start": 0.0, "end": 0.0, "hook": "", "reason": "", '
        f'"speaker_focus": "A|B|both"}}]\n\n'
        f"TRANSCRIPT:\n{transcript_text}"
    )


# --- Pure, testable helpers (no API, no IO) ---


def build_transcript_text(words: List[Dict[str, Any]]) -> str:
    """Render words as `[start] SPEAKER: text` lines, broken on speaker change
    and sentence-ending punctuation so Claude has timestamps to snap to."""
    lines: List[str] = []
    buf: List[str] = []
    start = 0.0
    speaker = ""

    def flush():
        if buf:
            lines.append(f"[{start:.1f}] {speaker}: {' '.join(buf)}")

    for w in words:
        if buf and w["speaker"] != speaker:
            flush()
            buf = []
        if not buf:
            start = float(w["start"])
            speaker = str(w["speaker"])
        buf.append(str(w["word"]))
        if str(w["word"]).rstrip().endswith((".", "!", "?")):
            flush()
            buf = []
    flush()
    return "\n".join(lines)


def extract_json_array(text: str) -> Any:
    """Parse a JSON array out of a model response, tolerating ``` fences/prose."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    lo, hi = s.find("["), s.rfind("]")
    if lo == -1 or hi == -1 or hi < lo:
        raise ValueError("no JSON array found in response")
    return json.loads(s[lo : hi + 1])


def snap_clip(
    start: float, end: float, words: List[Dict[str, Any]], duration: float
) -> Tuple[float, float]:
    """Snap start to the nearest real word start, end to nearest word end, clamp
    inside [0, duration], and nudge length into [MIN_LEN, MAX_LEN]."""
    starts = sorted({float(w["start"]) for w in words})
    ends = sorted({float(w["end"]) for w in words})

    s = min(starts, key=lambda x: abs(x - start))
    e = min(ends, key=lambda x: abs(x - end))
    s = max(0.0, min(s, duration))
    e = max(0.0, min(e, duration))

    if e <= s:
        e = min(duration, s + MIN_LEN)

    if e - s < MIN_LEN:
        target = min(duration, s + MIN_LEN)
        later = [x for x in ends if x >= target]
        e = later[0] if later else target
    if e - s > MAX_LEN:
        target = s + MAX_LEN
        earlier = [x for x in ends if x <= target and x > s]
        e = earlier[-1] if earlier else target

    return round(s, 3), round(e, 3)


def normalize_clips(
    raw: List[Dict[str, Any]],
    count: int,
    words: List[Dict[str, Any]],
    duration: float,
) -> List[Dict[str, Any]]:
    """Validate Claude's output and snap each clip to word boundaries."""
    if not isinstance(raw, list):
        raise ValueError("expected a JSON array of clips")
    if len(raw) < count:
        raise ValueError(f"expected {count} clips, got {len(raw)}")

    out: List[Dict[str, Any]] = []
    for c in raw[:count]:
        start = float(c.get("start", 0.0))
        end = float(c.get("end", 0.0))
        s, e = snap_clip(start, end, words, duration)
        focus = c.get("speaker_focus", "both")
        if focus not in ("A", "B", "both"):
            focus = "both"
        out.append(
            {
                "start": s,
                "end": e,
                "hook": str(c.get("hook", "")),
                "reason": str(c.get("reason", "")),
                "speaker_focus": focus,
            }
        )
    return out


# --- API + IO ---


def video_duration(job_id: str, words: List[Dict[str, Any]]) -> float:
    """ffprobe the source; fall back to the last word's end time."""
    src = source_path(job_id)
    if src.exists():
        try:
            out = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(src),
                ],
                check=True, capture_output=True, text=True,
            )
            return float(out.stdout.strip())
        except Exception:
            pass
    return max((float(w["end"]) for w in words), default=0.0)


def build_regen_prompt(
    transcript_text: str, duration: float, avoid: List[Dict[str, float]]
) -> str:
    ranges = ", ".join(f"{a['start']:.1f}-{a['end']:.1f}s" for a in avoid) or "none"
    return (
        f"Below is a transcript. Each line is `[start_seconds] SPEAKER: text`.\n"
        f"The video is {duration:.1f} seconds long.\n\n"
        f"Pick ONE new self-contained moment to cut into a vertical clip that does "
        f"NOT overlap these already-used ranges: {ranges}.\n"
        f"Rules:\n"
        f"- {int(MIN_LEN)}-{int(MAX_LEN)} seconds, within the video, start on a "
        f"clean sentence boundary.\n\n"
        f"Return ONLY a JSON array with exactly 1 object:\n"
        f'[{{"start": 0.0, "end": 0.0, "hook": "", "reason": "", '
        f'"speaker_focus": "A|B|both"}}]\n\n'
        f"TRANSCRIPT:\n{transcript_text}"
    )


def _call_claude(prompt: str) -> List[Dict[str, Any]]:
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    last_err: Exception | None = None
    for _ in range(2):  # one retry on parse failure
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        try:
            data = extract_json_array(text)
            if isinstance(data, list) and data:
                return data
            last_err = ValueError("empty or non-array JSON")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Claude did not return valid JSON: {last_err}")


def select(job_id: str, count: int) -> str:
    """Pick `count` clips from transcript.json, write clips.json, return its path."""
    tpath = transcript_path(job_id)
    if not tpath.exists():
        raise FileNotFoundError(f"transcript.json not found for job {job_id}")
    words = json.loads(tpath.read_text())
    if not words:
        raise ValueError("transcript is empty")

    duration = video_duration(job_id, words)
    transcript_text = build_transcript_text(words)
    raw = _call_claude(build_user_prompt(transcript_text, count, duration))
    clips = normalize_clips(raw, count, words, duration)

    out = clips_path(job_id)
    out.write_text(json.dumps(clips, ensure_ascii=False, indent=2))
    return str(out)


def regenerate_one(job_id: str, index: int) -> Dict[str, Any]:
    """Re-pick a single clip slot with a fresh, non-overlapping moment."""
    tpath, cpath = transcript_path(job_id), clips_path(job_id)
    if not cpath.exists():
        raise FileNotFoundError(f"clips.json not found for job {job_id}")
    if not tpath.exists():
        raise FileNotFoundError(f"transcript.json not found for job {job_id}")
    clips = json.loads(cpath.read_text())
    if index < 0 or index >= len(clips):
        raise IndexError(f"clip index {index} out of range (have {len(clips)})")
    words = json.loads(tpath.read_text())

    duration = video_duration(job_id, words)
    avoid = [
        {"start": c["start"], "end": c["end"]}
        for i, c in enumerate(clips)
        if i != index
    ]
    transcript_text = build_transcript_text(words)
    raw = _call_claude(build_regen_prompt(transcript_text, duration, avoid))
    new_clip = normalize_clips(raw, 1, words, duration)[0]

    clips[index] = new_clip
    cpath.write_text(json.dumps(clips, ensure_ascii=False, indent=2))
    return new_clip
