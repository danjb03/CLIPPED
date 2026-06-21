"""Unit tests for the pure split-screen logic (no MediaPipe, no ffmpeg).

Run from worker/:  python tests/test_split.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import split  # noqa: E402
from split import build_stack_cmd, panel_crop, split_faces  # noqa: E402


def test_split_two_clusters_left_right():
    # 4 faces on the left (~0.25), 4 on the right (~0.75)
    centers = [(0.24, 0.5), (0.26, 0.5), (0.25, 0.5), (0.23, 0.5)] + [
        (0.74, 0.5), (0.76, 0.5), (0.75, 0.5), (0.77, 0.5)
    ]
    res = split_faces(centers)
    assert res is not None
    top, bottom = res
    assert top[0] < bottom[0]  # left cluster first (goes on top)
    assert 0.23 <= top[0] <= 0.27 and 0.73 <= bottom[0] <= 0.77


def test_single_face_returns_none():
    centers = [(0.5, 0.5)] * 8  # all clustered together
    assert split_faces(centers) is None


def test_too_few_detections_returns_none():
    assert split_faces([(0.2, 0.5), (0.8, 0.5)]) is None  # < 2*min_support


def test_small_gap_returns_none():
    centers = [(0.48, 0.5)] * 4 + [(0.52, 0.5)] * 4  # gap < min_gap
    assert split_faces(centers) is None


def test_panel_crop_full_height_landscape():
    box = panel_crop(0.5, 0.5, 1920, 1080)  # 16:9 source
    assert box["h"] == 1080
    assert box["w"] == 1214  # 1080 * 1.125 = 1215 -> even
    assert box["x"] % 2 == 0 and box["w"] + box["x"] <= 1920


def test_panel_crop_clamps_to_left_edge():
    box = panel_crop(0.0, 0.5, 1920, 1080)  # face at far left
    assert box["x"] == 0


def test_panel_crop_tall_source_uses_width():
    box = panel_crop(0.5, 0.5, 1080, 1920)  # portrait source, w<h*aspect
    assert box["w"] == 1080
    assert box["h"] == 960  # 1080 / 1.125


def test_build_stack_cmd_has_vstack_and_two_crops():
    top = {"w": 1214, "h": 1080, "x": 100, "y": 0}
    bottom = {"w": 1214, "h": 1080, "x": 600, "y": 0}
    cmd = build_stack_cmd("/s.mp4", 5.0, 30.0, top, bottom, "/o.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert fc.count("crop=") == 2
    assert "vstack=inputs=2" in fc
    assert "scale=1080:960" in fc
    assert "-ss" in cmd and "5.000" in cmd


def test_make_stacked_base_falls_back_when_one_face(monkeypatch=None):
    # stub detection to report a single cluster -> should return False, not crash
    split.detect_face_centers = lambda *a, **k: ([(0.5, 0.5)] * 8, 1920, 1080)
    assert split.make_stacked_base("/x.mp4", 0.0, 10.0, "/out.mp4") is False


def test_make_stacked_base_runs_ffmpeg_for_two_faces():
    split.detect_face_centers = lambda *a, **k: (
        [(0.25, 0.5)] * 4 + [(0.75, 0.5)] * 4,
        1920,
        1080,
    )
    calls = []
    split._run_ffmpeg = lambda cmd: calls.append(cmd)
    assert split.make_stacked_base("/x.mp4", 0.0, 10.0, "/out.mp4") is True
    assert len(calls) == 1 and "vstack=inputs=2" in " ".join(calls[0])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
