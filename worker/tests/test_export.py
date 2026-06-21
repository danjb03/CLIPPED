"""Tests for Phase 6: copy generation (stubbed Claude) + export zip assembly.

Run from worker/:  python tests/test_export.py
"""

import json
import os
import pathlib
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import copygen  # noqa: E402
import exporter  # noqa: E402
import paths  # noqa: E402


def _setup_job():
    tmp = tempfile.mkdtemp()
    paths.OUTPUT_DIR = pathlib.Path(tmp)
    job = "job6"
    jd = paths.job_dir(job)
    (jd / "renders").mkdir(parents=True)
    words = [
        {"word": "hello", "start": 0.0, "end": 1.0, "speaker": "A"},
        {"word": "world", "start": 1.0, "end": 2.0, "speaker": "A"},
        {"word": "again", "start": 30.0, "end": 31.0, "speaker": "B"},
    ]
    clips = [
        {"start": 0.0, "end": 20.0, "hook": "h0", "reason": "r", "speaker_focus": "A"},
        {"start": 25.0, "end": 40.0, "hook": "h1", "reason": "r", "speaker_focus": "B"},
    ]
    paths.transcript_path(job).write_text(json.dumps(words))
    paths.clips_path(job).write_text(json.dumps(clips))
    (jd / "renders" / "clip_0.mp4").write_bytes(b"fake0")
    (jd / "renders" / "clip_1.mp4").write_bytes(b"fake1")
    return job


def test_segment_text_filters_by_window():
    words = [
        {"word": "hello", "start": 0.0, "end": 1.0},
        {"word": "world", "start": 1.0, "end": 2.0},
        {"word": "later", "start": 30.0, "end": 31.0},
    ]
    assert copygen.segment_text(words, 0.0, 20.0) == "hello world"


def test_build_copy_prompt_includes_hook_and_text():
    p = copygen.build_copy_prompt("some words", "my hook")
    assert "my hook" in p and "some words" in p


def test_generate_copy_attaches_copy(monkeypatch_done=False):
    job = _setup_job()
    copygen._ask_claude = lambda seg, hook: f"caption for {hook}"
    copygen.generate_copy(job)
    clips = json.loads(paths.clips_path(job).read_text())
    assert clips[0]["copy"] == "caption for h0"
    assert clips[1]["copy"] == "caption for h1"


def test_build_captions_txt_has_block_per_clip():
    clips = [
        {"start": 0.0, "end": 20.0, "hook": "h0", "copy": "cap zero"},
        {"start": 25.0, "end": 40.0, "hook": "h1", "copy": "cap one"},
    ]
    txt = exporter.build_captions_txt(clips)
    assert "clip_0.mp4" in txt and "clip_1.mp4" in txt
    assert "cap zero" in txt and "cap one" in txt
    assert "Hook: h0" in txt


def test_export_zip_contains_clips_and_captions():
    job = _setup_job()
    copygen._ask_claude = lambda seg, hook: f"cap {hook}"
    copygen.generate_copy(job)
    zip_path = exporter.export(job)

    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        assert "renders/clip_0.mp4" in names
        assert "renders/clip_1.mp4" in names
        assert "captions.txt" in names
        caps = z.read("captions.txt").decode()
    # every rendered clip has matching copy in the text file
    assert "cap h0" in caps and "cap h1" in caps


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
