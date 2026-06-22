"""Unit tests for the ASS caption builder (no ffmpeg)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from captions_ass import _ass_color, _ass_time, build_ass, group_words  # noqa: E402


def test_color_to_ass_bgr():
    assert _ass_color("#ffe600") == "&H0000E6FF"  # BGR with zero alpha
    assert _ass_color("#000000") == "&H00000000"


def test_time_format():
    assert _ass_time(0) == "0:00:00.00"
    assert _ass_time(75.5) == "0:01:15.50"


def test_group_words_breaks_on_gap_and_count():
    words = [{"word": f"w{i}", "start": i * 0.3, "end": i * 0.3 + 0.2} for i in range(6)]
    words.append({"word": "later", "start": 10.0, "end": 10.5})  # big gap
    groups = group_words(words)
    assert len(groups) == 3  # 5 + 1 (count break) then the gap word
    assert groups[-1][0]["word"] == "later"


def test_build_ass_has_styles_events_and_highlight():
    words = [
        {"word": "hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0},
    ]
    style = {"fontSize": 84, "color": "#ffffff", "highlightColor": "#ffe600",
             "strokeColor": "#000000", "strokeWidth": 10, "position": {"y": 0.78}}
    ass = build_ass(words, style)
    assert "[V4+ Styles]" in ass and "[Events]" in ass
    assert ass.count("Dialogue:") == 2  # one per word, no inter-word gap here
    assert "HELLO" in ass and "WORLD" in ass  # uppercased
    assert "00E6FF" in ass  # highlight colour (BGR) appears as an inline tag


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
