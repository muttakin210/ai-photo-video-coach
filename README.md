# 📸 AI Photo & Video Coach — MVP

An editor + honest feedback + platform-fit assistant, built from the project
guide. Upload a photo or video and it gives a **0–100 quality score**, an honest
verdict (**Bhalo / Thik ache / Kharap**) with tips, checks whether it fits each
social platform (Instagram Post/Story/Reels, YouTube, TikTok…), and can
**auto-crop** photos for any platform (face-aware).

This is **Option B** from the guide: a web app = React-style frontend + Python
**FastAPI** backend + **OpenCV**. The frontend here is plain HTML/CSS/JS (no build
step) so the whole thing runs with one command.

## MVP features implemented

| Feature | Status |
|---|---|
| Photo/Video upload | ✅ |
| Basic editor (brightness, contrast, saturation, rotate, grayscale, download) | ✅ (client-side canvas) |
| Quality score 0–100 (blur, brightness, contrast, noise, resolution) | ✅ |
| Good/Bad verdict with reasons | ✅ |
| Platform Fit Checker (ratio + resolution + video length) | ✅ |
| Auto Resize / Auto Crop (face-aware) | ✅ (photos) |
| Story safe-zone overlay | ✅ |
| Video analysis (duration, fps, shakiness, brightness) | ✅ |
| Platform rules as editable JSON config | ✅ `backend/config/platforms.json` |

Not yet (Phase 2/3 in the guide): live-camera shooting tips, caption/hashtag AI,
best-time-to-post, login/cloud save, AI aesthetic model (NIMA/CLIP) — there's a
`aesthetic_hook()` stub ready for it in `analysis.py`.

## Run it

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000**

### Optional: video convert
Video *analysis* works out of the box. Video *convert/export* to a platform size
needs **ffmpeg** on your PATH. Without it, the app still runs and shows
"video convert: off".

## Project layout

```
ai-photo-video-coach/
├── backend/
│   ├── main.py            # FastAPI app + serves the frontend
│   ├── analysis.py        # photo quality score/verdict/tips (OpenCV)
│   ├── image_ops.py       # face-aware auto-crop/resize (Pillow)
│   ├── video.py           # video analysis + ffmpeg convert
│   ├── platforms.py       # loads + checks platform rules
│   ├── config/platforms.json   # <- edit platform specs here, no code change
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## API

- `GET  /api/platforms` — list platform specs
- `POST /api/analyze` (multipart `file`) — score + verdict + tips + platform fit
- `POST /api/fit` (multipart `file`, `platform_id`, `fmt`) — auto-cropped image
- `GET  /health` — status + whether ffmpeg is available

## Tuning the coach
Thresholds (what counts as blurry/dark/noisy) live at the top of
`backend/analysis.py`. Platform sizes/ratios/length limits live in
`backend/config/platforms.json` — the guide recommends verifying these against
the official Instagram/YouTube help pages before launch.
