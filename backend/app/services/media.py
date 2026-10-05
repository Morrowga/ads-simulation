"""Upload handling: MIME sniffing, size limits, image re-encoding (strips metadata), ffprobe for video,
ffmpeg frame/audio extraction for the pipeline."""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps

from app.config import get_settings
from app.errors import ApiError, ErrorCode

IMAGE_MIMES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
VIDEO_MIMES = {"video/mp4": "mp4", "video/quicktime": "mov"}


@dataclass
class MediaInfo:
    kind: str
    mime: str
    ext: str
    data: bytes
    width: int | None
    height: int | None
    duration_s: float | None
    meta: dict[str, Any]


def sniff_mime(data: bytes) -> str | None:
    """Magic-byte sniffing; the client-provided content type is never trusted."""
    head = data[:16]
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) > 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"qt  ",):
            return "video/quicktime"
        return "video/mp4"
    return None


def process_image(data: bytes) -> MediaInfo:
    s = get_settings()
    if len(data) > s.MAX_IMAGE_BYTES:
        raise ApiError(
            ErrorCode.asset_too_large, f"Image is larger than {s.MAX_IMAGE_BYTES // (1024 * 1024)} MB"
        )
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # noqa: BLE001
        raise ApiError(ErrorCode.asset_invalid, "Image could not be decoded")
    img = ImageOps.exif_transpose(img)
    fmt = (img.format or "").upper()
    if fmt == "PNG" and img.mode in ("RGBA", "LA", "P"):
        out_fmt, mime, ext = "PNG", "image/png", "png"
        img = img.convert("RGBA")
    elif fmt == "WEBP":
        out_fmt, mime, ext = "WEBP", "image/webp", "webp"
        img = img.convert("RGB")
    else:
        out_fmt, mime, ext = "JPEG", "image/jpeg", "jpg"
        img = img.convert("RGB")
    max_side = 2048
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    save_kwargs: dict[str, Any] = {"optimize": True}
    if out_fmt == "JPEG":
        save_kwargs["quality"] = 90
    img.save(buf, format=out_fmt, **save_kwargs)  # re-encoding drops EXIF/XMP metadata
    clean = buf.getvalue()
    return MediaInfo(
        kind="image",
        mime=mime,
        ext=ext,
        data=clean,
        width=img.size[0],
        height=img.size[1],
        duration_s=None,
        meta={"original_bytes": len(data)},
    )


def _run(cmd: list[str], input_bytes: bytes | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=input_bytes, capture_output=True, timeout=timeout, check=False)


def ffprobe(path: str) -> dict[str, Any]:
    if shutil.which("ffprobe") is None:
        raise ApiError(
            ErrorCode.asset_invalid, "Video processing is not available on this server (ffprobe missing)"
        )
    proc = _run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], timeout=60
    )
    if proc.returncode != 0:
        raise ApiError(ErrorCode.asset_invalid, "Video could not be read")
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        raise ApiError(ErrorCode.asset_invalid, "Video metadata could not be parsed")


def process_video(data: bytes, mime: str) -> MediaInfo:
    s = get_settings()
    if len(data) > s.MAX_VIDEO_BYTES:
        raise ApiError(
            ErrorCode.asset_too_large, f"Video is larger than {s.MAX_VIDEO_BYTES // (1024 * 1024)} MB"
        )
    ext = VIDEO_MIMES[mime]
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as fh:
        fh.write(data)
        path = fh.name
    try:
        info = ffprobe(path)
    finally:
        os.unlink(path)
    video = next((st for st in info.get("streams", []) if st.get("codec_type") == "video"), None)
    audio = next((st for st in info.get("streams", []) if st.get("codec_type") == "audio"), None)
    if video is None:
        raise ApiError(ErrorCode.asset_invalid, "File has no video stream")
    duration = float(info.get("format", {}).get("duration") or video.get("duration") or 0.0)
    if duration <= 0:
        raise ApiError(ErrorCode.asset_invalid, "Video duration unknown")
    if duration > s.MAX_VIDEO_SECONDS:
        raise ApiError(
            ErrorCode.asset_invalid,
            f"Video is longer than {int(s.MAX_VIDEO_SECONDS)} seconds",
            details={"duration_s": duration},
        )
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    rotation = 0
    for sd in video.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    if rotation in (90, -90, 270, -270):
        width, height = height, width
    return MediaInfo(
        kind="video",
        mime=mime,
        ext=ext,
        data=data,
        width=width,
        height=height,
        duration_s=round(duration, 2),
        meta={
            "codec": video.get("codec_name"),
            "has_audio": audio is not None,
            "fps": video.get("avg_frame_rate"),
            "original_bytes": len(data),
        },
    )


def process_upload(data: bytes, filename: str | None) -> MediaInfo:
    mime = sniff_mime(data)
    if mime in IMAGE_MIMES:
        return process_image(data)
    if mime in VIDEO_MIMES:
        return process_video(data, mime)
    raise ApiError(
        ErrorCode.asset_invalid,
        "Unsupported file type: use jpg, png, webp, mp4 or mov",
        details={"filename": filename, "sniffed": mime},
    )


async def process_upload_async(data: bytes, filename: str | None) -> MediaInfo:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, process_upload, data, filename)


# --------------------------------------------------------------------------- pipeline helpers


def extract_frames(
    video_bytes: bytes, ext: str, duration_s: float, max_frames: int = 12
) -> list[tuple[float, bytes]]:
    """1 frame per second (max 12) plus 4 frames from the first 2 seconds (hook window). Returns (t, jpeg)."""
    if shutil.which("ffmpeg") is None:
        raise ApiError(ErrorCode.asset_invalid, "ffmpeg is not installed")
    times = [round(t, 2) for t in (0.0, 0.5, 1.0, 1.5)]
    step_times = [float(t) for t in range(0, int(min(duration_s, max_frames)))]
    for t in step_times:
        if t not in times:
            times.append(t)
    times = sorted(set(t for t in times if t < duration_s))[: max_frames + 4]
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as fh:
        fh.write(video_bytes)
        path = fh.name
    frames: list[tuple[float, bytes]] = []
    try:
        for t in times:
            proc = _run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-ss",
                    f"{t:.2f}",
                    "-i",
                    path,
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale='min(768,iw)':-2",
                    "-f",
                    "image2pipe",
                    "-vcodec",
                    "mjpeg",
                    "-q:v",
                    "4",
                    "-",
                ],
                timeout=60,
            )
            if proc.returncode == 0 and proc.stdout:
                frames.append((t, proc.stdout))
    finally:
        os.unlink(path)
    return frames


def extract_audio(video_bytes: bytes, ext: str) -> bytes | None:
    if shutil.which("ffmpeg") is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as fh:
        fh.write(video_bytes)
        path = fh.name
    try:
        proc = _run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                path,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-b:a",
                "64k",
                "-f",
                "mp3",
                "-",
            ],
            timeout=120,
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        return proc.stdout
    finally:
        os.unlink(path)
