"""Phase 1 — transcribe (faster-whisper) + diarise (pyannote), locally and free.

Produces transcript.json = [{word, start, end, speaker}] with speaker labels
"A", "B", ... assigned in order of first appearance.

faster-whisper gives word-level timestamps. pyannote.audio gives speaker turns.
We align each word to the speaker turn it overlaps most. Diarisation is optional:
if no HUGGINGFACE_TOKEN is set or pyannote fails, every word falls back to a
single speaker "A" (the run still succeeds, just without a speaker split).
"""

import json
import logging
import os
import subprocess
from typing import Dict, List, Tuple

from paths import audio_path, source_path, transcript_path

log = logging.getLogger("transcribe")

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")
DIARIZATION_MODEL = os.environ.get(
    "DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1"
)


# --- Pure, testable alignment logic (no models, no IO) ---

Word = Dict[str, object]
Segment = Tuple[float, float, str]


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def assign_speakers(words: List[Word], segments: List[Segment]) -> List[Word]:
    """Attach a `speaker` to each word from the most-overlapping diarisation turn.

    Words overlapping no turn (e.g. between turns) take the nearest turn by
    midpoint. With no segments at all, everything becomes speaker "A".
    """
    if not segments:
        return [{**w, "speaker": "A"} for w in words]

    out: List[Word] = []
    for w in words:
        ws, we = float(w["start"]), float(w["end"])
        best_label, best_ov = None, 0.0
        for s0, s1, label in segments:
            ov = _overlap(ws, we, s0, s1)
            if ov > best_ov:
                best_ov, best_label = ov, label
        if best_label is None:
            mid = (ws + we) / 2
            best_label = min(
                segments, key=lambda s: abs(((s[0] + s[1]) / 2) - mid)
            )[2]
        out.append({**w, "speaker": best_label})
    return out


def relabel_speakers(words: List[Word]) -> List[Word]:
    """Remap raw labels (e.g. SPEAKER_01) to A, B, C... by first appearance."""
    mapping: Dict[str, str] = {}
    for w in words:
        sp = str(w["speaker"])
        if sp not in mapping:
            mapping[sp] = chr(ord("A") + len(mapping))
    return [{**w, "speaker": mapping[str(w["speaker"])]} for w in words]


# --- Model + IO ---


def _extract_audio(job_id: str) -> str:
    src = source_path(job_id)
    if not src.exists():
        raise FileNotFoundError(f"source.mp4 not found for job {job_id}")
    out = audio_path(job_id)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", "-vn", str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    return str(out)


def _whisper_words(wav: str) -> List[Word]:
    from faster_whisper import WhisperModel

    model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    segments, _info = model.transcribe(wav, word_timestamps=True)
    words: List[Word] = []
    for seg in segments:
        for wd in seg.words or []:
            text = wd.word.strip()
            if not text:
                continue
            words.append(
                {"word": text, "start": round(wd.start, 3), "end": round(wd.end, 3)}
            )
    return words


def _diarize(wav: str) -> List[Segment]:
    token = os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        log.warning("HUGGINGFACE_TOKEN not set — skipping diarisation (single speaker).")
        return []
    try:
        from pyannote.audio import Pipeline

        pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL, use_auth_token=token)
        diar = pipeline(wav)
        return [
            (turn.start, turn.end, label)
            for turn, _, label in diar.itertracks(yield_label=True)
        ]
    except Exception as e:  # never let diarisation crash the run
        log.warning("diarisation failed (%s) — falling back to single speaker.", e)
        return []


def transcribe(job_id: str) -> str:
    """Transcribe + diarise source.mp4, write transcript.json, return its path."""
    wav = _extract_audio(job_id)
    words = _whisper_words(wav)
    segments = _diarize(wav)
    words = assign_speakers(words, segments)
    words = relabel_speakers(words)

    out = transcript_path(job_id)
    out.write_text(json.dumps(words, ensure_ascii=False, indent=2))
    return str(out)
