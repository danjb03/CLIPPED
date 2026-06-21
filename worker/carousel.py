"""Carousel storyline generation with Claude (the user's prompt).

POST /carousels {job_id} feeds the full transcript to Claude using the creator's
"Split Screen Carousel Storyline" prompt and extracts 6-10 carousel storylines,
each with an internal title and 4 slides. Saved as carousels.json (structured)
and carousels.txt (the raw, postable format), both under output/<job_id>/.

This is a separate artifact from the video pipeline: it produces text carousels,
not timestamped video clips.
"""

import json
import os
import re
from typing import Any, Dict, List

from paths import job_dir, transcript_path

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# --- The creator's prompt (verbatim intent; bullet glyphs normalised) ---
SYSTEM_PROMPT = """You are a social media content strategist working on a personal brand in the business and entrepreneurship space. The creator is Neil — an entrepreneur who shares business advice, ideas, and personal struggle stories. His content is aspirational.

I'm going to paste a full podcast transcript. Your job is to extract 6-10 carousel storylines from it.

For each carousel:
- Give it a title (internal use only, not for the slide)
- Write 4 slides
- Each slide = 2 key sentences max
- Pull only from what's actually said in the transcript — no invented content, no paraphrasing that changes the meaning
- The sentences should flow as a story arc: hook, build, tension or insight, payoff
- Think: what's the most compelling thing he said that could stop someone mid-scroll?

Format each one like this:
Carousel [number]: [internal title]
Slide 1: [sentence. sentence.]
Slide 2: [sentence. sentence.]
Slide 3: [sentence. sentence.]
Slide 4: [sentence. sentence.]

Prioritise moments where Neil:
- Shares a struggle or failure
- Gives a counter-intuitive business take
- Drops a specific number, result, or timeline
- Says something that would make someone stop and think

Do not repeat the same idea across carousels. Each one should feel like a standalone story."""


# --- Pure, testable helpers (no API, no IO) ---


def transcript_plaintext(words: List[Dict[str, Any]]) -> str:
    """Speaker-labelled transcript text (no timestamps) for the prompt."""
    lines: List[str] = []
    buf: List[str] = []
    speaker = ""
    for w in words:
        if buf and str(w["speaker"]) != speaker:
            lines.append(f"{speaker}: {' '.join(buf)}")
            buf = []
        if not buf:
            speaker = str(w["speaker"])
        buf.append(str(w["word"]))
    if buf:
        lines.append(f"{speaker}: {' '.join(buf)}")
    return "\n".join(lines)


def parse_carousels(text: str) -> List[Dict[str, Any]]:
    """Parse the `Carousel N: ...` / `Slide N: ...` format into structured data."""
    carousels: List[Dict[str, Any]] = []
    cur: Dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"(?i)^carousel\s*\[?(\d+)\]?\s*:\s*(.*)$", line)
        if m:
            if cur:
                carousels.append(cur)
            cur = {"number": int(m.group(1)), "title": m.group(2).strip(), "slides": []}
            continue
        s = re.match(r"(?i)^slide\s*\[?(\d+)\]?\s*:\s*(.*)$", line)
        if s and cur is not None:
            cur["slides"].append(s.group(2).strip())
    if cur:
        carousels.append(cur)
    return carousels


def render_carousels_txt(carousels: List[Dict[str, Any]]) -> str:
    """Render structured carousels back to the postable text format."""
    blocks: List[str] = []
    for c in carousels:
        lines = [f"Carousel {c['number']}: {c['title']}"]
        for i, slide in enumerate(c.get("slides", []), start=1):
            lines.append(f"Slide {i}: {slide}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


# --- API + IO ---


def _ask_claude(transcript_text: str) -> str:
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript_text}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def generate(job_id: str) -> str:
    """Generate carousels from transcript.json; write carousels.json + .txt."""
    tpath = transcript_path(job_id)
    if not tpath.exists():
        raise FileNotFoundError(f"transcript.json not found for job {job_id}")
    words = json.loads(tpath.read_text())
    if not words:
        raise ValueError("transcript is empty")

    transcript_text = transcript_plaintext(words)

    carousels: List[Dict[str, Any]] = []
    for _ in range(2):  # one retry if nothing parses
        text = _ask_claude(transcript_text)
        carousels = parse_carousels(text)
        if carousels:
            break
    if not carousels:
        raise RuntimeError("Claude returned no parseable carousels")

    jd = job_dir(job_id)
    (jd / "carousels.json").write_text(json.dumps(carousels, ensure_ascii=False, indent=2))
    (jd / "carousels.txt").write_text(render_carousels_txt(carousels))
    return str(jd / "carousels.json")
