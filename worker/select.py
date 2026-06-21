"""Phase 2 — clip selection with Claude.

Feeds the timestamped transcript to Claude, returns N segments as strict JSON:
  [{"start", "end", "hook", "reason", "speaker_focus": "A|B|both"}]
Snaps starts to word boundaries; segments 15-60s. Stub: implemented in Phase 2.

TODO: paste the user's selection prompt here.
"""


def select(job_id: str, count: int) -> str:
    """Pick `count` clips from transcript.json, write clips.json, return its path."""
    raise NotImplementedError("Phase 2: Claude clip selection")
