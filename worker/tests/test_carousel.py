"""Tests for carousel generation: parsing, plaintext, stubbed generate, export.

Run from worker/:  python tests/test_carousel.py
"""

import json
import os
import pathlib
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import carousel  # noqa: E402
import exporter  # noqa: E402
import paths  # noqa: E402

SAMPLE = """Here are the carousels:

Carousel 1: The first failure
Slide 1: I lost everything. It was brutal.
Slide 2: But I kept going. Day by day.
Slide 3: Then it clicked. The numbers turned.
Slide 4: We hit 1m in a year. Worth it.

Carousel 2: Counter-intuitive take
Slide 1: Stop chasing customers. Seriously.
Slide 2: Make them come to you. It works.
Slide 3: I doubted it too. Then I tried.
Slide 4: Revenue tripled. No ad spend.
"""


def test_parse_carousels_structure():
    out = carousel.parse_carousels(SAMPLE)
    assert len(out) == 2
    assert out[0]["number"] == 1
    assert out[0]["title"] == "The first failure"
    assert len(out[0]["slides"]) == 4
    assert out[1]["slides"][0] == "Stop chasing customers. Seriously."


def test_parse_handles_bracketed_format():
    text = "Carousel [3]: Title here\nSlide [1]: a. b.\nSlide [2]: c. d."
    out = carousel.parse_carousels(text)
    assert out[0]["number"] == 3 and len(out[0]["slides"]) == 2


def test_transcript_plaintext_groups_speakers():
    words = [
        {"word": "hello", "speaker": "A", "start": 0, "end": 1},
        {"word": "there", "speaker": "A", "start": 1, "end": 2},
        {"word": "hi", "speaker": "B", "start": 2, "end": 3},
    ]
    txt = carousel.transcript_plaintext(words)
    assert txt == "A: hello there\nB: hi"


def test_dominant_speaker():
    words = [
        {"word": "a", "speaker": "A", "start": 0, "end": 1},
        {"word": "b", "speaker": "A", "start": 1, "end": 2},
        {"word": "c", "speaker": "B", "start": 2, "end": 3},
    ]
    assert carousel.dominant_speaker(words) == "A"


def test_build_name_map_two_speakers():
    words = [
        {"word": "a", "speaker": "A", "start": 0, "end": 1},
        {"word": "b", "speaker": "B", "start": 1, "end": 2},
    ]
    nm = carousel.build_name_map(words, "B")
    assert nm == {"B": "Neil", "A": "Guest"}


def test_transcript_plaintext_applies_name_map():
    words = [
        {"word": "hi", "speaker": "A", "start": 0, "end": 1},
        {"word": "yo", "speaker": "B", "start": 1, "end": 2},
    ]
    txt = carousel.transcript_plaintext(words, {"A": "Neil", "B": "Guest"})
    assert txt == "Neil: hi\nGuest: yo"


def test_render_round_trips():
    out = carousel.parse_carousels(SAMPLE)
    rendered = carousel.render_carousels_txt(out)
    assert "Carousel 1: The first failure" in rendered
    assert "Slide 4: Revenue tripled. No ad spend." in rendered


def _setup_job():
    tmp = tempfile.mkdtemp()
    paths.OUTPUT_DIR = pathlib.Path(tmp)
    job = "jobc"
    jd = paths.job_dir(job)
    (jd / "renders").mkdir(parents=True)
    paths.transcript_path(job).write_text(
        json.dumps([{"word": "x", "speaker": "A", "start": 0, "end": 1}])
    )
    (jd / "renders" / "clip_0.mp4").write_bytes(b"fake")
    paths.clips_path(job).write_text(json.dumps([{"start": 0, "end": 20, "hook": "h"}]))
    return job


def test_generate_writes_files():
    job = _setup_job()
    carousel._ask_claude = lambda t: SAMPLE
    carousel.generate(job)
    data = json.loads((paths.job_dir(job) / "carousels.json").read_text())
    assert len(data) == 2
    assert (paths.job_dir(job) / "carousels.txt").exists()


def test_export_includes_carousels():
    job = _setup_job()
    carousel._ask_claude = lambda t: SAMPLE
    carousel.generate(job)
    zip_path = exporter.export(job)
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    assert "carousels.txt" in names and "carousels.json" in names
    assert "renders/clip_0.mp4" in names and "captions.txt" in names


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
