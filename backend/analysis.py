"""
Photo analysis engine for AI Photo & Video Coach.

Implements the "Quality Score" and "Good/Bad Verdict" features from the guide:
blur, brightness, contrast, noise, resolution, face/subject and composition
checks -> a 0-100 score, a verdict, and human tips (Banglish + English).

Uses only OpenCV + NumPy so it runs anywhere without a GPU. The AI aesthetic
model (NIMA/CLIP) from the guide is left as a documented hook (aesthetic_hook).
"""

from __future__ import annotations

import os
import cv2
import numpy as np

# Haar cascade ships inside the opencv package, so face detection needs no
# download. Load defensively: some OpenCV builds omit the classic objdetect
# module, in which case face detection is simply skipped (score still works).
def _load_face_cascade():
    try:
        path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        cascade = cv2.CascadeClassifier(path)
        return cascade if not cascade.empty() else None
    except Exception:
        return None


_FACE_CASCADE = _load_face_cascade()


def detect_faces(gray: np.ndarray):
    """Return a list of (x, y, w, h) faces, or [] if detection is unavailable."""
    if _FACE_CASCADE is None:
        return []
    h, w = gray.shape
    found = _FACE_CASCADE.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5,
        minSize=(max(24, w // 20), max(24, h // 20)),
    )
    return [(int(x), int(y), int(fw), int(fh)) for (x, y, fw, fh) in found]

# Thresholds. Tuning these changes how strict the coach is.
BLUR_MIN = 100.0          # Laplacian variance below this = blurry
DARK_MAX = 60.0           # mean brightness below this = too dark
BRIGHT_MAX = 200.0        # mean brightness above this = too bright
CONTRAST_MIN = 40.0       # std dev below this = flat / low contrast
NOISE_MAX = 12.0          # estimated noise sigma above this = grainy
RES_MIN = 1080            # shorter side below this = low resolution for social


def _metrics(bgr: np.ndarray) -> dict:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))

    # Noise estimate: difference between the image and a median-blurred copy.
    denoised = cv2.medianBlur(gray, 3)
    noise = float(np.std(gray.astype(np.float32) - denoised.astype(np.float32)))

    faces = detect_faces(gray)
    return {
        "width": w,
        "height": h,
        "blur": round(blur, 1),
        "brightness": round(brightness, 1),
        "contrast": round(contrast, 1),
        "noise": round(noise, 2),
        "faces": [[x, y, fw, fh] for (x, y, fw, fh) in faces],
        "aspect_ratio": round(w / h, 4) if h else 0,
    }


def _composition(m: dict) -> dict:
    """Rough rule-of-thirds check on the largest detected face/subject."""
    w, h, faces = m["width"], m["height"], m["faces"]
    if not faces:
        return {"has_subject": False, "centered": None, "on_thirds": None}
    # Largest face = main subject.
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    cx, cy = (x + fw / 2) / w, (y + fh / 2) / h
    # Distance to the nearest rule-of-thirds intersection.
    thirds = [(tx, ty) for tx in (1 / 3, 2 / 3) for ty in (1 / 3, 2 / 3)]
    d_thirds = min(((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5 for tx, ty in thirds)
    d_center = ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5
    # Subject touching an edge -> likely cropped.
    edge_cut = x <= 2 or y <= 2 or (x + fw) >= w - 2 or (y + fh) >= h - 2
    return {
        "has_subject": True,
        "subject_center": [round(cx, 3), round(cy, 3)],
        "centered": d_center < 0.12,
        "on_thirds": d_thirds < 0.12,
        "edge_cut": bool(edge_cut),
    }


def aesthetic_hook(bgr: np.ndarray) -> float | None:
    """
    Placeholder for the guide's AI aesthetic score (NIMA / CLIP).
    Return a 0-100 float once a model is wired in; None means "not available"
    and the rule-based score is used alone.
    """
    return None


def analyze_image(bgr: np.ndarray) -> dict:
    if bgr is None or bgr.size == 0:
        raise ValueError("Could not read image data.")

    m = _metrics(bgr)
    comp = _composition(m)
    score = 100
    tips: list[dict] = []

    def flag(penalty, category, bn, en):
        nonlocal score
        score -= penalty
        tips.append({"category": category, "bn": bn, "en": en, "penalty": penalty})

    if m["blur"] < BLUR_MIN:
        flag(30, "blur", "Chhobi jhapsha. Focus kore abar tulun.",
             "Photo looks blurry. Refocus and reshoot.")
    if m["brightness"] < DARK_MAX:
        flag(25, "brightness", "Khub andhokar. Aro alo-te tulun.",
             "Too dark. Shoot in more light.")
    elif m["brightness"] > BRIGHT_MAX:
        flag(20, "brightness", "Khub bright / over-exposed. Alo kom korun.",
             "Too bright / over-exposed. Reduce the light.")
    if m["contrast"] < CONTRAST_MIN:
        flag(12, "contrast", "Chhobi flat lagche, contrast barun.",
             "Image looks flat. Increase contrast.")
    if m["noise"] > NOISE_MAX:
        flag(12, "noise", "Kom alo-te tola, noise/grain beshi.",
             "Shot in low light. Too much noise/grain.")
    if min(m["width"], m["height"]) < RES_MIN:
        flag(15, "resolution", "Resolution kom. Insta-te quality kharap dekhabe.",
             "Low resolution. Will look poor on Instagram.")

    if comp["has_subject"]:
        if comp.get("edge_cut"):
            flag(15, "composition", "Mukh/subject kete geche. Frame-e purota rakhun.",
                 "Face/subject is cut off. Keep it fully in frame.")
        elif not comp["centered"] and not comp["on_thirds"]:
            flag(6, "composition", "Subject majhkhane ba rule-of-thirds-e nei.",
                 "Subject isn't centered or on a rule-of-thirds point.")
    # No face is not always bad (landscapes etc.), so it is a hint, not a penalty.

    aesthetic = aesthetic_hook(bgr)
    if aesthetic is not None:
        score = round(0.6 * score + 0.4 * aesthetic)

    score = max(0, min(100, score))
    if score >= 75:
        verdict, verdict_bn = "Good", "Bhalo"
    elif score >= 50:
        verdict, verdict_bn = "Okay", "Thik ache"
    else:
        verdict, verdict_bn = "Bad", "Kharap - abar tulun"

    if not tips:
        tips.append({"category": "ok", "bn": "Darun! Ei chhobi post korar jonno ready.",
                     "en": "Great! This photo is ready to post.", "penalty": 0})

    return {
        "type": "photo",
        "score": score,
        "verdict": verdict,
        "verdict_bn": verdict_bn,
        "metrics": m,
        "composition": comp,
        "tips": tips,
        "aesthetic_score": aesthetic,
    }


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Unsupported or corrupt image file.")
    return img
