from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class TtsCachePaths:
    cache_key: str
    raw_clip: Path
    prepared_clip: Path
    fitted_clip: Path


TTS_TIMELINE_CACHE_VERSION = "v3"


def tts_cache_key(
    *,
    speaker_id: str,
    voice: str,
    voice_cache_salt: str = "",
    rate: str,
    pitch: str,
    volume: str,
    text: str,
    global_speed: float = 1.0,
) -> str:
    payload = f"{speaker_id}|{voice}|{voice_cache_salt}|{rate}|{pitch}|{volume}|{text}|{global_speed}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def tts_fit_key(*, cache_key: str, target_ms: int, timing_mode: str) -> str:
    return hashlib.sha1(f"{cache_key}|{target_ms}|{timing_mode}|{TTS_TIMELINE_CACHE_VERSION}".encode("utf-8")).hexdigest()[:12]


def build_tts_cache_paths(
    *,
    tts_dir: Path,
    index: int,
    speaker_id: str,
    voice: str,
    voice_cache_salt: str = "",
    rate: str,
    pitch: str,
    volume: str,
    text: str,
    raw_extension: str,
    target_ms: int,
    timing_mode: str,
    global_speed: float = 1.0,
) -> TtsCachePaths:
    cache_key = tts_cache_key(
        speaker_id=speaker_id,
        voice=voice,
        voice_cache_salt=voice_cache_salt,
        rate=rate,
        pitch=pitch,
        volume=volume,
        text=text,
        global_speed=global_speed,
    )
    raw_stem = f"{index:04d}_{cache_key}"
    if raw_extension == ".wav":
        raw_clip = tts_dir / f"{raw_stem}_raw{raw_extension}"
    else:
        raw_clip = tts_dir / f"{raw_stem}{raw_extension}"
    fit_key = tts_fit_key(cache_key=cache_key, target_ms=target_ms, timing_mode=timing_mode)
    return TtsCachePaths(
        cache_key=cache_key,
        raw_clip=raw_clip,
        prepared_clip=tts_dir / f"{index:04d}_{cache_key}_timeline_{TTS_TIMELINE_CACHE_VERSION}.wav",
        fitted_clip=tts_dir / f"{index:04d}_{cache_key}_{fit_key}.wav",
    )
