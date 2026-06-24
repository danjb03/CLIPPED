"""Unit tests for the split-screen carousel slide helpers (no ffmpeg)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from carousel_render import (  # noqa: E402
    find_sentence_time,
    split_sentences,
    wrap,
)


def test_split_sentences_basic():
    assert split_sentences("First one. Second one.") == ["First one.", "Second one."]


def test_split_sentences_pads_single():
    assert split_sentences("Only one.") == ["Only one.", "Only one."]


def test_split_sentences_truncates_extra():
    out = split_sentences("A. B. C.")
    assert out == ["A.", "B."]


def test_find_sentence_time_exact_match():
    transcript = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0},
        {"word": "this", "start": 1.0, "end": 1.4},
        {"word": "is", "start": 1.4, "end": 1.7},
        {"word": "great", "start": 1.7, "end": 2.2},
    ]
    assert find_sentence_time("this is great", transcript) == 1.0


def test_find_sentence_time_handles_punctuation():
    transcript = [
        {"word": "At", "start": 0.0, "end": 0.3},
        {"word": "19", "start": 0.3, "end": 0.7},
        {"word": "years", "start": 0.7, "end": 1.1},
        {"word": "old", "start": 1.1, "end": 1.5},
        {"word": "I", "start": 1.5, "end": 1.7},
    ]
    assert find_sentence_time("At 19 years old, ...", transcript) == 0.0


def test_find_sentence_time_fallback():
    transcript = [
        {"word": "Something", "start": 5.0, "end": 6.0},
        {"word": "else", "start": 6.0, "end": 7.0},
    ]
    # No match -> falls back to best-effort idx 0
    assert find_sentence_time("totally unrelated", transcript) == 5.0


def test_wrap_breaks_long_lines():
    out = wrap("one two three four five six seven", max_chars=12)
    assert "\n" in out
    for line in out.split("\n"):
        assert len(line) <= 14  # +word slack


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
