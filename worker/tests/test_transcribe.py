"""Unit tests for the pure word<->speaker alignment logic (no models, no IO).

Run from worker/:  python -m pytest tests/   (or)  python tests/test_transcribe.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcribe import assign_speakers, relabel_speakers  # noqa: E402


def _words(*spans):
    return [{"word": f"w{i}", "start": s, "end": e} for i, (s, e) in enumerate(spans)]


def test_assign_by_max_overlap():
    words = _words((0.0, 0.5), (0.6, 1.0), (2.1, 2.5))
    segments = [(0.0, 1.0, "SPEAKER_00"), (2.0, 3.0, "SPEAKER_01")]
    out = assign_speakers(words, segments)
    assert [w["speaker"] for w in out] == ["SPEAKER_00", "SPEAKER_00", "SPEAKER_01"]


def test_word_between_turns_takes_nearest():
    words = _words((1.4, 1.6))  # gap between the two turns, closer to the second
    segments = [(0.0, 1.0, "SPEAKER_00"), (1.5, 3.0, "SPEAKER_01")]
    out = assign_speakers(words, segments)
    assert out[0]["speaker"] == "SPEAKER_01"


def test_no_segments_falls_back_to_single_speaker():
    words = _words((0.0, 0.5), (0.6, 1.0))
    out = assign_speakers(words, [])
    assert [w["speaker"] for w in out] == ["A", "A"]


def test_relabel_by_first_appearance():
    words = [
        {"word": "a", "start": 0, "end": 1, "speaker": "SPEAKER_01"},
        {"word": "b", "start": 1, "end": 2, "speaker": "SPEAKER_00"},
        {"word": "c", "start": 2, "end": 3, "speaker": "SPEAKER_01"},
    ]
    out = relabel_speakers(words)
    assert [w["speaker"] for w in out] == ["A", "B", "A"]


def test_full_pipeline_two_speakers():
    words = _words((0.0, 0.5), (0.6, 1.0), (2.1, 2.5), (2.6, 3.0))
    segments = [(0.0, 1.0, "SPEAKER_07"), (2.0, 3.0, "SPEAKER_03")]
    out = relabel_speakers(assign_speakers(words, segments))
    labels = [w["speaker"] for w in out]
    assert labels == ["A", "A", "B", "B"]
    assert len(set(labels)) == 2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
