"""Unit tests for the pure render helpers (no ffmpeg, no Remotion).

Run from worker/:  python tests/test_render.py
"""

import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paths  # noqa: E402
import render  # noqa: E402
from render import (  # noqa: E402
    build_carousel_props,
    build_ffmpeg_cmd,
    build_props,
    slice_words,
)


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


def test_build_carousel_props_merges_style():
    props = build_carousel_props("hi there", 2, 4, {"accent": "#fff", "color": "#000"})
    assert props["text"] == "hi there"
    assert props["index"] == 2 and props["total"] == 4
    assert props["accent"] == "#fff"


def test_render_carousels_writes_one_png_per_slide():
    tmp = tempfile.mkdtemp()
    paths.OUTPUT_DIR = pathlib.Path(tmp)
    job = "jobr"
    jd = paths.job_dir(job)
    jd.mkdir(parents=True)
    (jd / "carousels.json").write_text(
        json.dumps(
            [
                {"number": 1, "title": "t", "slides": ["a", "b", "c", "d"]},
                {"number": 2, "title": "u", "slides": ["e", "f"]},
            ]
        )
    )
    # stub the actual Remotion still render: just create the output file
    render._remotion_still = lambda props_file, out: pathlib.Path(out).write_bytes(b"png")
    out = render.render_carousels(job)
    assert len(out) == 6  # 4 + 2 slides
    assert (jd / "carousels" / "carousel_1" / "slide_1.png").exists()
    assert (jd / "carousels" / "carousel_2" / "slide_2.png").exists()
    # props temp files cleaned up
    assert not list((jd / "carousels" / "carousel_1").glob(".props_*.json"))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
