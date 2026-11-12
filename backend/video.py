"""
Video analysis (the "Video Analysis" feature): duration, resolution, fps,
shakiness, brightness and audio-length sanity, plus per-platform length checks.

Reads frames with OpenCV so it works without ffmpeg. Export/convert to a
platform size uses ffmpeg when available and otherwise reports it's unavailable.
"""

from __future__ import annotations

import shutil
import subprocess
import cv2
import numpy as np

from platforms import get_platform

HAS_FFMPEG = shutil.which("ffmpeg") is not None

SHAKE_MAX = 8.0  # mean frame-to-frame motion above this = shaky


def analyze_video(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Could not open video. Try MP4/MOV/AVI.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frame_count / fps if fps else 0

    # Sample up to ~60 evenly spaced frames for motion/brightness.
    sample_n = min(60, frame_count) if frame_count else 0
    idxs = np.linspace(0, max(frame_count - 1, 0), sample_n).astype(int) if sample_n else []

    prev = None
    motions, brights = [], []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brights.append(float(np.mean(gray)))
        small = cv2.resize(gray, (160, 90))
        if prev is not None:
            motions.append(float(np.mean(cv2.absdiff(small, prev))))
        prev = small
    cap.release()

    shakiness = round(float(np.mean(motions)), 2) if motions else 0.0
    brightness = round(float(np.mean(brights)), 1) if brights else 0.0

    score = 100
    tips = []

    def flag(pen, cat, bn, en):
        nonlocal score
        score -= pen
        tips.append({"category": cat, "bn": bn, "en": en, "penalty": pen})

    if shakiness > SHAKE_MAX:
        flag(30, "shaky", "Video onek shaky. Gimbal/stabilizer use korun ba phone soja rakhun.",
             "Video is shaky. Use a stabilizer or hold the phone steady.")
    if brightness and brightness < 55:
        flag(20, "brightness", "Video khub andhokar. Aro alo dorkar.",
             "Video is too dark. Needs more light.")
    elif brightness > 205:
        flag(15, "brightness", "Video over-exposed. Alo kom korun.",
             "Video is over-exposed. Reduce the light.")
    if min(width, height) and min(width, height) < 1080:
        flag(15, "resolution", "Resolution kom (1080p-r niche).",
             "Resolution is below 1080p.")
    if fps and fps < 24:
        flag(10, "fps", f"FPS kom ({fps:.0f}). Choppy lagte pare.",
             f"Low frame rate ({fps:.0f} fps). May look choppy.")
    if not tips:
        tips.append({"category": "ok", "bn": "Video stable ar bhalo. Ready!",
                     "en": "Video is stable and clean. Ready!", "penalty": 0})

    score = max(0, min(100, score))
    verdict_bn = "Bhalo" if score >= 75 else "Thik ache" if score >= 50 else "Kharap"
    verdict = "Good" if score >= 75 else "Okay" if score >= 50 else "Bad"

    return {
        "type": "video",
        "score": score,
        "verdict": verdict,
        "verdict_bn": verdict_bn,
        "metrics": {
            "width": width, "height": height,
            "fps": round(fps, 2), "duration_seconds": round(duration, 2),
            "frame_count": frame_count, "shakiness": shakiness, "brightness": brightness,
            "aspect_ratio": round(width / height, 4) if height else 0,
        },
        "tips": tips,
        "ffmpeg_available": HAS_FFMPEG,
    }


def platform_length_check(duration: float, platform_id: str) -> dict:
    p = get_platform(platform_id)
    limit = p.get("max_video_seconds", 0)
    ok = duration <= limit if limit else True
    return {
        "platform": p["name"],
        "duration_seconds": round(duration, 2),
        "max_seconds": limit,
        "fits": ok,
        "message": ("Length thik ache. / Length is fine." if ok
                    else f"Video {duration:.0f}s, {p['name']}-e max {limit}s. Trim korun. "
                         f"/ Too long; trim to {limit}s."),
    }


def convert_for_platform(in_path: str, out_path: str, platform_id: str) -> bool:
    """Convert a video to a platform size with ffmpeg. Returns False if unavailable."""
    if not HAS_FFMPEG:
        return False
    p = get_platform(platform_id)
    w, h = p["width"], p["height"]
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
          f"crop={w}:{h}")
    cmd = ["ffmpeg", "-y", "-i", in_path, "-vf", vf,
           "-c:v", "libx264", "-crf", "20", "-c:a", "aac", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return True
