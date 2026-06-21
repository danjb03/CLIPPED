"""Phase 4 — split-screen (static two-face stack).

Sample frames, MediaPipe face detection, cluster into 2 stable regions, crop each
to 1080x960 and vstack to 1080x1920. Falls back to single 9:16 crop if 2 stable
faces aren't found — never crashes. Stub: implemented in Phase 4.
"""


def stack_two_faces(job_id: str, start: float, end: float) -> str:
    """Produce a stacked 1080x1920 clip for [start, end]; fall back to single crop."""
    raise NotImplementedError("Phase 4: split-screen face stack")
