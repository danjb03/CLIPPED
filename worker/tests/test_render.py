"""Unit tests for the pure render helpers (no ffmpeg, no Remotion).

Run from worker/:  python tests/test_render.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from render import build_ffmpeg_cmd, build_props, slice_words  # noqa: E402


def _words():
    return [
        {"word": "a", "start": 0.0, "end": 1.0, "speaker": "A"},
        {"word": "b", "start": 9.5, "end": 10.5, "speaker": "A"},  # straddles end
        {"word": "c", "start": 12.0, "end": 13.0, "speaker": "B"},
        {"word": "d", "start": 20.0, "end": 21.0, "speaker": "B"},
    ]


def test_slice_keeps_overlapping_words_and_rebases():
    out = slice_words(_words(), 10.0, 20.0)  # window [10,20)
    # "a" excluded; "b" straddles start (overlaps) -> kept; "c" kept; "d" excluded.
    assert [w["word"] for w in out] == ["b", "c"]
    # rebased relative to start=10
    assert out[0]["start"] == 0.0  # max(0, 9.5-10) clamped
    assert out[0]["end"] == 0.5
    assert out[1]["start"] == 2.0 and out[1]["end"] == 3.0


def test_slice_preserves_speaker():
    out = slice_words(_words(), 11.0, 14.0)
    assert out[0]["speaker"] == "B"


def test_ffmpeg_cmd_has_crop_seek_and_duration():
    cmd = build_ffmpeg_cmd("/x/source.mp4", 12.5, 30.0, "/x/out.mp4")
    assert "-ss" in cmd and "12.500" in cmd
    assert "-t" in cmd and "30.000" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "crop=" in vf and "scale=1080:1920" in vf


def test_build_props_shape():
    props = build_props("clips/j_0.mp4", _words(), 30.0, {"fontSize": 84})
    assert props["videoSrc"] == "clips/j_0.mp4"
    assert props["durationInSeconds"] == 30.0
    assert "fps" in props and props["style"]["fontSize"] == 84
    assert isinstance(props["words"], list)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
