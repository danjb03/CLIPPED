"""Shared filesystem layout helpers. Everything lives under output/<job_id>/."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"


def job_dir(job_id: str) -> Path:
    return OUTPUT_DIR / job_id


def source_path(job_id: str) -> Path:
    return job_dir(job_id) / "source.mp4"


def audio_path(job_id: str) -> Path:
    return job_dir(job_id) / "audio.wav"


def transcript_path(job_id: str) -> Path:
    return job_dir(job_id) / "transcript.json"


def clips_path(job_id: str) -> Path:
    return job_dir(job_id) / "clips.json"
