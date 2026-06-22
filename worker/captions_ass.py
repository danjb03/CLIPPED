"""Build an ASS subtitle file for word-synced captions, burned by ffmpeg.

This replaces the (slow, memory-heavy) headless-Chrome/Remotion render for clips:
ffmpeg's subtitles filter draws these in near real-time using a fraction of the
memory, so it's fast even on a small box. Style mirrors the Remotion look: bold
white, dark outline, lower-third, with the active word highlighted.
"""

from typing import Any, Dict, List

W, H = 1080, 1920


def _hex_rgb(hex_color: str) -> tuple[str, str, str]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return h[0:2].upper(), h[2:4].upper(), h[4:6].upper()


def _ass_color(hex_color: str) -> str:
    """#RRGGBB -> &H00BBGGRR (ASS style colour, with zero alpha)."""
    r, g, b = _hex_rgb(hex_color)
    return f"&H00{b}{g}{r}"


def _inline_c(hex_color: str) -> str:
    """Inline primary-colour override tag {\\c&HBBGGRR&}."""
    r, g, b = _hex_rgb(hex_color)
    return "{\\c&H" + f"{b}{g}{r}" + "&}"


def _ass_time(t: float) -> str:
    if t < 0:
        t = 0.0
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def group_words(
    words: List[Dict[str, Any]], max_words: int = 5, max_gap: float = 0.7
) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    for w in words:
        if not cur:
            cur = [w]
            continue
        if len(cur) >= max_words or float(w["start"]) - float(cur[-1]["end"]) > max_gap:
            groups.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def _group_text(group, active_idx, color_hex, highlight_hex) -> str:
    base = _inline_c(color_hex)
    hi = _inline_c(highlight_hex)
    parts = []
    for j, w in enumerate(group):
        word = _esc(str(w["word"]).upper())
        parts.append(hi + word + base if j == active_idx else word)
    return " ".join(parts)


def build_ass(words: List[Dict[str, Any]], style: Dict[str, Any]) -> str:
    fontsize = int(style.get("fontSize", 84))
    primary_hex = style.get("color", "#ffffff")
    outline_hex = style.get("strokeColor", "#000000")
    highlight_hex = style.get("highlightColor", "#ffe600")
    outline_w = max(1, round(float(style.get("strokeWidth", 10)) / 2))
    pos_y = float(style.get("position", {}).get("y", 0.78))
    margin_v = max(10, round((1 - pos_y) * H))
    font = style.get("assFont", "Liberation Sans")

    primary = _ass_color(primary_hex)
    outline = _ass_color(outline_hex)

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},{fontsize},{primary},{primary},{outline},"
        f"&H64000000,-1,0,0,0,100,100,0,0,1,{outline_w},2,2,80,80,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]

    events: List[str] = []
    for group in group_words(words):
        for i, w in enumerate(group):
            text = _group_text(group, i, primary_hex, highlight_hex)
            events.append(
                f"Dialogue: 0,{_ass_time(float(w['start']))},"
                f"{_ass_time(float(w['end']))},Cap,,0,0,0,,{text}"
            )
            if i + 1 < len(group):
                gs, ge = float(w["end"]), float(group[i + 1]["start"])
                if ge > gs:
                    plain = _group_text(group, -1, primary_hex, highlight_hex)
                    events.append(
                        f"Dialogue: 0,{_ass_time(gs)},{_ass_time(ge)},Cap,,0,0,0,,{plain}"
                    )

    return "\n".join(header + events) + "\n"
