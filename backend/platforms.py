"""Loads and serves the platform rules from config/platforms.json."""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG = Path(__file__).parent / "config" / "platforms.json"


def load_platforms() -> list[dict]:
    data = json.loads(_CONFIG.read_text(encoding="utf-8"))
    return data["platforms"]


def get_platform(platform_id: str) -> dict:
    for p in load_platforms():
        if p["id"] == platform_id:
            return p
    raise KeyError(f"Unknown platform '{platform_id}'")


def check_fit(width: int, height: int, platform_id: str) -> dict:
    """Compare an image/video's dimensions against a platform's target."""
    p = get_platform(platform_id)
    ratio = width / height if height else 0
    target = p["ratio_value"]
    # Tolerance ~2% so near-perfect ratios still pass.
    diff = abs(ratio - target) / target if target else 1
    ratio_ok = diff <= 0.02
    res_ok = min(width, height) >= min(p["width"], p["height"])

    messages = []
    if not ratio_ok:
        messages.append(
            f"Ratio {ratio:.3f} target {target:.3f} ({p['ratio']}) er shathe mile na. "
            f"Auto-crop diye thik korun. / Ratio doesn't match {p['ratio']}; use Auto-crop."
        )
    if not res_ok:
        messages.append(
            f"Resolution kom (min side {min(width, height)}px, dorkar {min(p['width'], p['height'])}px). "
            f"/ Resolution below the recommended {p['width']}x{p['height']}."
        )
    if not messages:
        messages.append("Perfect fit! Ei platform-er jonno ready. / Ready for this platform.")

    return {
        "platform": p,
        "fits": ratio_ok and res_ok,
        "ratio_ok": ratio_ok,
        "resolution_ok": res_ok,
        "source_ratio": round(ratio, 4),
        "messages": messages,
    }
