from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .process_utils import run, run_output


def resolve_ffprobe_timeout(default: float = 60.0) -> float:
    raw_value = str(os.environ.get("DUB_FFPROBE_TIMEOUT") or "").strip()
    if not raw_value:
        return max(default, 10.0)
    try:
        return max(float(raw_value), 10.0)
    except ValueError:
        return max(default, 10.0)


def run_ffprobe_output(cmd: list[str], *, path: Path, timeout: float) -> str:
    attempts = [max(timeout, 10.0), max(timeout * 2.0, 60.0)]
    last_error: Exception | None = None
    for attempt_timeout in attempts:
        try:
            return run_output(cmd, timeout=attempt_timeout)
        except subprocess.TimeoutExpired as exc:
            last_error = exc
            continue
    raise RuntimeError(
        f"ffprobe timed out for {path} after {attempts[-1]:.1f}s. "
        "Set DUB_FFPROBE_TIMEOUT to a higher value if this video is very large or on a slow drive."
    ) from last_error


def ffprobe_json(path: Path, timeout: float | None = None) -> dict[str, Any]:
    effective_timeout = resolve_ffprobe_timeout(timeout or 60.0)
    raw = run_ffprobe_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        path=path,
        timeout=effective_timeout,
    )
    return json.loads(raw)


def ffprobe_duration_ms(path: Path) -> int:
    probe = ffprobe_json(path)
    duration = float(probe.get("format", {}).get("duration", 0.0))
    return int(duration * 1000)


def ffprobe_audio_duration_ms(path: Path, timeout: float | None = None) -> int:
    if not path.exists():
        raise RuntimeError(f"TTS audio file was not created: {path}")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"TTS audio file is empty: {path}")
    effective_timeout = resolve_ffprobe_timeout(timeout or 30.0)
    raw = run_ffprobe_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        path=path,
        timeout=effective_timeout,
    )
    return int(float(raw) * 1000)


def validate_generated_audio_file(path: Path, *, context: str) -> None:
    if not path.exists():
        raise RuntimeError(f"{context}: audio file was not created at {path}")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"{context}: audio file is empty at {path}")


def get_video_meta(path: Path) -> dict[str, Any]:
    probe = ffprobe_json(path)
    video_stream = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), {})
    audio_stream = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"), {})
    width = int(video_stream.get("width") or 1080)
    height = int(video_stream.get("height") or 1920)
    frame_rate_raw = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "30/1"
    try:
        numerator, denominator = frame_rate_raw.split("/")
        fps = float(numerator) / max(float(denominator), 1.0)
    except Exception:
        fps = 30.0
    duration_ms = int(float(probe.get("format", {}).get("duration", 0.0)) * 1000)
    bitrate = int(probe.get("format", {}).get("bit_rate") or 0)
    return {
        "path": str(path),
        "filename": path.name,
        "width": width,
        "height": height,
        "durationMs": duration_ms,
        "fps": round(fps, 3),
        "bitrate": bitrate,
        "hasAudio": bool(audio_stream),
        "sizeBytes": int(probe.get("format", {}).get("size", 0) or 0),
    }


def extract_thumbnail(video_path: Path, thumbnail_path: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "0.2",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-update",
            "1",
            "-vf",
            "scale=540:-2",
            str(thumbnail_path),
        ],
        timeout=30.0
    )


def extract_audio_for_whisperx(video_path: Path, audio_path: Path) -> None:
    if audio_path.exists() and audio_path.stat().st_size > 0:
        return
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ],
        timeout=180.0
    )


def extract_gray_frame(video_path: Path, time_ms: int, sample_width: int, sample_height: int) -> bytes:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(time_ms, 0) / 1000:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            f"format=gray,scale={sample_width}:{sample_height}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5.0
    )
    return completed.stdout
