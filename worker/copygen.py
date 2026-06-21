"""Phase 6 — per-clip post copy with Claude.

NOTE: named copygen.py (not copy.py) because a module named `copy` on the
worker's sys.path shadows Python's stdlib `copy`, which FastAPI imports.

Stub: implemented in Phase 6. TODO: paste the user's copy prompt here.
"""


def generate_copy(job_id: str) -> str:
    """Generate post copy per clip, attach to clips.json, return its path."""
    raise NotImplementedError("Phase 6: Claude copy generation")
