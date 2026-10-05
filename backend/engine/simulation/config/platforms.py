"""Per-platform habits and helpers (usage by age, active hours, placement spec checks)."""

from __future__ import annotations

from typing import Any

import numpy as np

from engine.simulation.types import AGE_BANDS, PlatformConfig, age_band_label

DEFAULT_PEAK_HOURS = [
    0.25, 0.15, 0.08, 0.05, 0.05, 0.10, 0.30, 0.55, 0.70, 0.65, 0.60, 0.70,
    0.85, 0.75, 0.65, 0.65, 0.70, 0.85, 1.00, 1.00, 0.95, 0.85, 0.65, 0.40,
]  # fmt: skip


def peak_hours(platform: PlatformConfig) -> np.ndarray:
    raw = platform.market.get("peak_hours") or platform.behavior.get("peak_hours") or DEFAULT_PEAK_HOURS
    arr = np.array([float(x) for x in raw], dtype=np.float32)
    if arr.shape[0] != 24:
        arr = np.array(DEFAULT_PEAK_HOURS, dtype=np.float32)
    return arr / max(float(arr.max()), 1e-6)


def user_share_by_age(platform: PlatformConfig) -> np.ndarray:
    raw = platform.market.get("user_share_by_age") or {}
    out = np.zeros(len(AGE_BANDS), dtype=np.float32)
    for i in range(len(AGE_BANDS)):
        label = age_band_label(i)
        v = raw.get(label)
        if v is None:
            # fall back to a reasonable curve: younger bands use more
            v = [0.55, 0.85, 0.85, 0.8, 0.7, 0.55, 0.35][i]
        out[i] = float(v)
    return np.clip(out, 0.0, 1.0)


def sessions_per_day(platform: PlatformConfig, rng: np.random.Generator, n: int) -> np.ndarray:
    mean = float(platform.behavior.get("sessions_per_day", 6.0))
    return np.clip(rng.gamma(shape=3.0, scale=mean / 3.0, size=n), 0.5, 40.0).astype(np.float32)


def spec_check(platform: PlatformConfig, placement: str, asset: dict[str, Any]) -> tuple[bool, str]:
    """Factual check of an asset against a placement spec. Returns (ok, message)."""
    spec = platform.placement_spec(placement)
    if spec is None:
        return True, f"{platform.name}: placement '{placement}' has no published spec; not checked."
    kind = asset.get("kind")
    width, height = asset.get("width") or 0, asset.get("height") or 0
    duration = asset.get("duration_s")
    formats = [str(f) for f in spec.get("formats", [])]
    messages: list[str] = []
    ok = True
    if formats and kind not in formats:
        ok = False
        messages.append(
            f"{kind} is not accepted in {platform.name} {placement} (accepts {', '.join(formats)})"
        )
    ratios = [str(r) for r in spec.get("ratios", [])]
    if ratios and width and height:
        ratio = width / height
        fits = False
        for r in ratios:
            try:
                a, b = (float(x) for x in r.split(":"))
            except ValueError:
                continue
            if abs(ratio - a / b) / (a / b) <= 0.06:
                fits = True
                break
        if not fits:
            ok = False
            closest = f"{width}x{height} (~{ratio:.2f}:1)"
            messages.append(
                f"{closest} does not match the {platform.name} {placement} ratios {', '.join(ratios)}; "
                f"it will show with bars or be cropped"
            )
    video_s = spec.get("video_s")
    if kind == "video" and duration is not None and video_s and len(video_s) == 2:
        lo, hi = float(video_s[0]), float(video_s[1])
        if duration < lo or duration > hi:
            ok = False
            messages.append(
                f"video length {duration:.1f}s is outside the {platform.name} {placement} range {lo:.0f}-{hi:.0f}s"
            )
    if ok:
        return True, f"{platform.name} {placement}: {kind} {width}x{height} matches the spec"
    return False, "; ".join(messages)
