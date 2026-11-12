"""
Auto-resize / auto-crop for each platform (the "Auto Resize / Auto Crop" MVP
feature). Crop is face/subject-aware: it keeps detected faces in frame instead
of a dumb center crop.
"""

from __future__ import annotations

import io
import cv2
import numpy as np
from PIL import Image

from analysis import detect_faces
from platforms import get_platform


def _subject_center(bgr: np.ndarray) -> tuple[float, float]:
    """Return the (x, y) focus point in 0..1, biased to faces if any."""
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = detect_faces(gray)
    if len(faces):
        # Weighted center of all faces.
        pts = [(x + fw / 2, y + fh / 2, fw * fh) for (x, y, fw, fh) in faces]
        tw = sum(p[2] for p in pts)
        cx = sum(p[0] * p[2] for p in pts) / tw
        cy = sum(p[1] * p[2] for p in pts) / tw
        return cx / w, cy / h
    return 0.5, 0.5


def smart_crop(bgr: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Scale to cover the target box, then crop toward the subject center."""
    h, w = bgr.shape[:2]
    scale = max(target_w / w, target_h / h)
    new_w, new_h = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    fx, fy = _subject_center(bgr)
    # Center the crop on the subject, clamped to image bounds.
    cx, cy = fx * new_w, fy * new_h
    x0 = int(round(cx - target_w / 2))
    y0 = int(round(cy - target_h / 2))
    x0 = max(0, min(x0, new_w - target_w))
    y0 = max(0, min(y0, new_h - target_h))
    return resized[y0:y0 + target_h, x0:x0 + target_w]


def fit_for_platform(bgr: np.ndarray, platform_id: str, fmt: str = "JPEG") -> tuple[bytes, dict]:
    p = get_platform(platform_id)
    out = smart_crop(bgr, p["width"], p["height"])
    rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    save_kwargs = {"quality": 95} if fmt.upper() in ("JPEG", "JPG") else {}
    Image.fromarray(rgb).save(buf, format="PNG" if fmt.upper() == "PNG" else "JPEG", **save_kwargs)
    return buf.getvalue(), {"width": p["width"], "height": p["height"], "platform": p["name"]}
