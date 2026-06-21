"""Unit tests for the pure clip-selection logic (no Claude, no IO).

Run from worker/:  python tests/test_select.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clipselect import (  # noqa: E402
    build_transcript_text,
    extract_json_array,
    normalize_clips,
    snap_clip,
)


def _words():
    # 0..100s, one word per second, speaker flips at 50s.
    out = []
    for i in range(100):
        out.append(
            {
                "word": f"w{i}" + (". " if i % 10 == 9 else ""),
                "start": float(i),
                "end": float(i) + 0.9,
                "speaker": "A" if i < 50 else "B",
            }
        )
    return out


def test_extract_json_handles_fences_and_prose():
    text = 'Sure!\n```json\n[{"start": 1.0, "end": 2.0}]\n```\nDone.'
    data = extract_json_array(text)
    assert data == [{"start": 1.0, "end": 2.0}]


def test_extract_json_bare_array():
    assert extract_json_array('[{"a": 1}]') == [{"a": 1}]


def test_snap_start_lands_on_a_word_boundary():
    words = _words()
    starts = {w["start"] for w in words}
    s, e = snap_clip(10.4, 35.6, words, duration=100.0)
    assert s in starts  # start is a real word start
    assert s == 10.0


def test_snap_enforces_min_length():
    words = _words()
    s, e = snap_clip(10.0, 12.0, words, duration=100.0)  # asked for 2s
    assert e - s >= 15.0


def test_snap_enforces_max_length():
    words = _words()
    s, e = snap_clip(5.0, 95.0, words, duration=100.0)  # asked for 90s
    assert e - s <= 60.0 + 1e-6


def test_snap_clamps_to_duration():
    words = _words()
    s, e = snap_clip(80.0, 200.0, words, duration=100.0)
    assert e <= 100.0


def test_normalize_returns_exactly_count_and_valid_focus():
    words = _words()
    raw = [
        {"start": 2.0, "end": 40.0, "speaker_focus": "A", "hook": "h", "reason": "r"},
        {"start": 55.0, "end": 90.0, "speaker_focus": "weird"},
        {"start": 10.0, "end": 30.0, "speaker_focus": "both"},
    ]
    clips = normalize_clips(raw, count=2, words=words, duration=100.0)
    assert len(clips) == 2
    assert clips[1]["speaker_focus"] == "both"  # invalid coerced to "both"
    starts = {w["start"] for w in words}
    for c in clips:
        assert c["start"] in starts
        assert 0 <= c["start"] < c["end"] <= 100.0


def test_normalize_rejects_too_few():
    try:
        normalize_clips([{"start": 0, "end": 20}], count=3, words=_words(), duration=100.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for too few clips")


def test_build_transcript_text_has_timestamps_and_speakers():
    text = build_transcript_text(_words())
    assert "[0.0] A:" in text
    assert "B:" in text  # speaker change rendered


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
