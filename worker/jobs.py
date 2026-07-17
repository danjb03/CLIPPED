"""Simple in-memory job tracker for the background pipeline.

Each /run call starts a background worker that walks the pipeline; the UI polls
/jobs/<id> for status. Survives a single process, which is all we need (single
worker, no DB by design).
"""

import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


STAGES = ["Download", "Transcribe", "Select", "Render", "Copy"]


@dataclass
class Job:
    id: str
    step: int = -1            # index into stages; -1 = not started
    state: str = "pending"    # pending | running | done | error
    stage: Optional[str] = None
    error: Optional[str] = None
    job_id: Optional[str] = None  # the worker job_id (output/<job_id>/)
    stages: List[str] = field(default_factory=lambda: list(STAGES))
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "step": self.step,
            "state": self.state,
            "stage": self.stage,
            "error": self.error,
            "job_id": self.job_id,
            "stages": self.stages,
            "elapsed": round((self.finished_at or time.time()) - self.started_at, 1),
        }


_jobs: Dict[str, Job] = {}
_lock = threading.Lock()


def create(run_id: str, *, job_id: Optional[str] = None) -> Job:
    with _lock:
        j = Job(id=run_id, job_id=job_id)
        _jobs[run_id] = j
        return j


def get(run_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(run_id)


def update(run_id: str, **kw) -> None:
    with _lock:
        j = _jobs.get(run_id)
        if not j:
            return
        for k, v in kw.items():
            setattr(j, k, v)


def run_pipeline(
    run_id: str,
    steps: List[tuple[str, Callable[[Job], None]]],
) -> None:
    """Walk `steps` (label, fn) updating job state; capture errors and stop."""
    update(run_id, state="running", stages=[label for label, _ in steps])
    for i, (label, fn) in enumerate(steps):
        update(run_id, step=i, stage=label)
        try:
            fn(get(run_id))  # type: ignore[arg-type]
        except Exception as e:
            tb = traceback.format_exc(limit=2)
            update(
                run_id,
                state="error",
                error=f"{label} failed: {e}\n{tb}",
                finished_at=time.time(),
            )
            return
    update(run_id, state="done", step=len(steps), stage=None, finished_at=time.time())
