"""Phase 4 — split-screen (static two-face stack).

Sample frames from a clip, detect faces with MediaPipe, cluster them into two
stable regions (left/right), crop each to 1080x960 and vstack into 1080x1920.
Captions (Phase 3) then render over the stacked output unchanged.

Never crashes: if two stable faces aren't found (or anything goes wrong), the
caller falls back to a single 9:16 centre crop.
"""

import logging
import subprocess
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("split")

SAMPLE_COUNT = 12
PANEL_W, PANEL_H = 1080, 960
PANEL_ASPECT = PANEL_W / PANEL_H  # 1.125

Center = Tuple[float, float]  # (cx, cy) normalised 0..1
CropBox = Dict[str, int]  # {w, h, x, y} in pixels


# --- Pure, testable geometry/clustering (no model, no ffmpeg) ---


def _median(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def split_faces(
    centers: List[Center], min_gap: float = 0.12, min_support: int = 3
) -> Optional[Tuple[Center, Center]]:
    """Cluster face centers into two by the largest horizontal gap.

    Returns (top, bottom) representative centers ordered left→right (left on top),
    or None if there aren't two well-separated, well-supported clusters.
    """
    if len(centers) < 2 * min_support:
        return None
    by_x = sorted(centers, key=lambda c: c[0])
    xs = [c[0] for c in by_x]

    gap, idx = max((xs[i + 1] - xs[i], i) for i in range(len(xs) - 1))
    if gap < min_gap:
        return None

    left, right = by_x[: idx + 1], by_x[idx + 1 :]
    if len(left) < min_support or len(right) < min_support:
        return None

    rep_left = (_median([c[0] for c in left]), _median([c[1] for c in left]))
    rep_right = (_median([c[0] for c in right]), _median([c[1] for c in right]))
    return rep_left, rep_right


def _even(n: int) -> int:
    return n - (n % 2)


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(v, hi))


def panel_crop(
    cx: float, cy: float, frame_w: int, frame_h: int, aspect: float = PANEL_ASPECT
) -> CropBox:
    """Largest panel-aspect crop around (cx, cy), clamped to the frame."""
    h = frame_h
    w = round(h * aspect)
    if w <= frame_w:
        x = _clamp(round(cx * frame_w - w / 2), 0, frame_w - w)
        y = 0
    else:
        w = frame_w
        h = round(w / aspect)
        x = 0
        y = _clamp(round(cy * frame_h - h / 2), 0, frame_h - h)
    return {"w": _even(w), "h": _even(h), "x": _even(x), "y": _even(y)}


def build_stack_cmd(
    src: str, start: float, duration: float, top: CropBox, bottom: CropBox, out: str
) -> List[str]:
    fc = (
        f"[0:v]crop={top['w']}:{top['h']}:{top['x']}:{top['y']},"
        f"scale={PANEL_W}:{PANEL_H},setsar=1[t];"
        f"[0:v]crop={bottom['w']}:{bottom['h']}:{bottom['x']}:{bottom['y']},"
        f"scale={PANEL_W}:{PANEL_H},setsar=1[b];"
        f"[t][b]vstack=inputs=2[v]"
    )
    return [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-filter_complex", fc,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(out),
    ]


# --- Model + ffmpeg ---


def _run_ffmpeg(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def detect_face_centers(
    src: str, start: float, duration: float, n: int = SAMPLE_COUNT
) -> Tuple[List[Center], int, int]:
    """Sample n frames in [start, start+duration] and return normalised face
    centers plus the frame (w, h). Lazy-imports cv2 + mediapipe."""
    import cv2  # type: ignore
    import mediapipe as mp  # type: ignore

    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0

    centers: List[Center] = []
    detector = mp.solutions.face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=0.5
    )
    try:
        for i in range(n):
            t = start + duration * (i + 0.5) / n
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = detector.process(rgb)
            for det in res.detections or []:
                box = det.location_data.relative_bounding_box
                centers.append((box.xmin + box.width / 2, box.ymin + box.height / 2))
    finally:
        detector.close()
        cap.release()
    return centers, frame_w, frame_h


def make_stacked_base(src: str, start: float, duration: float, out: str) -> bool:
    """Build a 1080x1920 two-face stack for [start, start+duration] at `out`.

    Returns True on success, False if two stable faces aren't found or anything
    fails (so the caller can fall back to a single crop). Never raises.
    """
    try:
        centers, frame_w, frame_h = detect_face_centers(src, start, duration)
        if not frame_w or not frame_h:
            return False
        clusters = split_faces(centers)
        if clusters is None:
            log.info("split-screen: two stable faces not found, falling back.")
            return False
        (top_c, bottom_c) = clusters
        top = panel_crop(top_c[0], top_c[1], frame_w, frame_h)
        bottom = panel_crop(bottom_c[0], bottom_c[1], frame_w, frame_h)
        _run_ffmpeg(build_stack_cmd(src, start, duration, top, bottom, out))
        return True
    except Exception as e:  # never crash the render
        log.warning("split-screen failed (%s) — falling back to single crop.", e)
        return False
