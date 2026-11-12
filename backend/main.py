"""
AI Photo & Video Coach - FastAPI backend.

Run:  uvicorn main:app --reload   (from the backend/ folder)
Then open http://127.0.0.1:8000
"""

from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

import analysis
import image_ops
import video
from platforms import load_platforms, check_fit

app = FastAPI(title="AI Photo & Video Coach", version="0.1.0 (MVP)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_BYTES = 100 * 1024 * 1024  # 100 MB upload cap


@app.get("/health")
def health():
    return {"status": "ok", "ffmpeg": video.HAS_FFMPEG}


@app.get("/api/platforms")
def platforms():
    return {"platforms": load_platforms()}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 100 MB).")
    if not data:
        raise HTTPException(400, "Empty file.")

    if ext in IMAGE_EXTS:
        try:
            bgr = analysis.decode_image(data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        result = analysis.analyze_image(bgr)
        w, h = result["metrics"]["width"], result["metrics"]["height"]
        result["platform_fit"] = [check_fit(w, h, p["id"]) for p in load_platforms()]
        return result

    if ext in VIDEO_EXTS:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            result = video.analyze_video(tmp_path)
            dur = result["metrics"]["duration_seconds"]
            w, h = result["metrics"]["width"], result["metrics"]["height"]
            result["platform_fit"] = [
                {**check_fit(w, h, p["id"]),
                 "length": video.platform_length_check(dur, p["id"])}
                for p in load_platforms()
            ]
            return result
        finally:
            os.unlink(tmp_path)

    raise HTTPException(400, f"Unsupported file type '{ext}'. "
                            f"Images: {sorted(IMAGE_EXTS)}, Videos: {sorted(VIDEO_EXTS)}")


@app.post("/api/fit")
async def fit(file: UploadFile = File(...), platform_id: str = Form(...),
              fmt: str = Form("JPEG")):
    """Auto-crop/resize a photo for a platform and return the new image."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in IMAGE_EXTS:
        raise HTTPException(400, "Auto-fit currently supports images only "
                                 "(video convert needs ffmpeg).")
    data = await file.read()
    try:
        bgr = analysis.decode_image(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        out_bytes, meta = image_ops.fit_for_platform(bgr, platform_id, fmt)
    except KeyError as e:
        raise HTTPException(404, str(e))
    media = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    filename = f"{platform_id}.{ 'png' if fmt.upper()=='PNG' else 'jpg' }"
    return Response(content=out_bytes, media_type=media,
                    headers={"Content-Disposition": f'inline; filename="{filename}"',
                             "X-Fit-Width": str(meta["width"]),
                             "X-Fit-Height": str(meta["height"])})


@app.post("/api/fit_all")
async def fit_all(file: UploadFile = File(...), fmt: str = Form("JPEG")):
    """Auto-crop a photo for EVERY platform and return them all in one ZIP."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in IMAGE_EXTS:
        raise HTTPException(400, "Fit-all currently supports images only.")
    data = await file.read()
    try:
        bgr = analysis.decode_image(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    is_png = fmt.upper() == "PNG"
    sub = "png" if is_png else "jpg"
    buf = io.BytesIO()
    manifest = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in load_platforms():
            img_bytes, meta = image_ops.fit_for_platform(bgr, p["id"], fmt)
            fname = f"{p['id']}_{meta['width']}x{meta['height']}.{sub}"
            zf.writestr(fname, img_bytes)
            manifest.append(f"{p['name']}: {fname} ({p['ratio']})")
        zf.writestr("README.txt",
                    "AI Photo & Video Coach - auto-fitted images\n\n" + "\n".join(manifest))
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="all_platforms.zip"'})


# Serve the frontend (index.html + assets) at the root.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
