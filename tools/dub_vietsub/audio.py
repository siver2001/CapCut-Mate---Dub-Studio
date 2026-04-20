from __future__ import annotations

import asyncio
import time
from pathlib import Path

import edge_tts
import srt
from pydub import AudioSegment

from .config import DEFAULT_VOICES, TEMP_DIR
from .io_utils import ffprobe_duration_ms, run
from .models import ClipManifest
from .text import clean_tts_text, normalize_text


def estimate_rate(text: str, target_ms: int) -> str:
    target_ms = max(target_ms, 900)
    target_seconds = target_ms / 1000
    expected_seconds = max(len(text) / 7.2, 1.5)
    ratio = expected_seconds / target_seconds
    percent = int((ratio - 1) * 100)
    percent = max(-6, min(percent, 6))
    return f"{percent:+d}%"


async def generate_tts(text: str, voice: str, rate: str, output_path: Path) -> None:
    communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicator.save(str(output_path))
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("TTS output is empty")


def synthesize_with_fallback(
    text: str,
    preferred_voice: str,
    voices: list[str],
    rate: str,
    output_path: Path,
) -> tuple[str, str]:
    voice_candidates = [preferred_voice] + [voice for voice in voices if voice != preferred_voice]
    rate_candidates = [rate, "-10%", "-5%", "+0%", "+8%"]
    text_candidates = [clean_tts_text(text)]
    if len(text_candidates[0]) > 220:
        text_candidates.append(text_candidates[0][:220])

    last_error: Exception | None = None
    for voice in voice_candidates:
        for candidate_text in text_candidates:
            if not candidate_text:
                continue
            for candidate_rate in rate_candidates:
                try:
                    asyncio.run(generate_tts(candidate_text, voice, candidate_rate, output_path))
                    return voice, candidate_rate
                except Exception as exc:  # pragma: no cover
                    last_error = exc
                    time.sleep(1.2)
    raise RuntimeError(f"TTS failed for text: {text[:80]}") from last_error


def build_atempo_filter(speed_factor: float) -> str:
    factor = max(speed_factor, 0.5)
    filters: list[str] = []
    while factor > 2.0:
        filters.append("atempo=2.0")
        factor /= 2.0
    while factor < 0.5:
        filters.append("atempo=0.5")
        factor /= 0.5
    filters.append(f"atempo={factor:.4f}")
    return ",".join(filters)


def fit_audio_length(source_path: Path, output_path: Path, target_ms: int) -> int:
    clip = AudioSegment.from_file(source_path)
    clip_ms = len(clip)
    target_fill_ms = int(target_ms * 0.94)
    target_fill_ms = max(target_fill_ms, 700)
    if abs(clip_ms - target_fill_ms) <= 120:
        clip.export(output_path, format="wav")
        return clip_ms

    speed_factor = clip_ms / max(target_fill_ms, 1)
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-filter:a",
            build_atempo_filter(speed_factor),
            str(output_path),
        ]
    )
    fitted = AudioSegment.from_file(output_path)
    if len(fitted) > target_ms:
        fitted = fitted[:target_ms]
        fitted.export(output_path, format="wav")
    elif len(fitted) < target_fill_ms:
        fitted += AudioSegment.silent(duration=target_fill_ms - len(fitted))
        fitted.export(output_path, format="wav")
    return len(fitted)


def create_dub_audio(
    video_path: Path,
    vietnamese_subtitles: list[srt.Subtitle],
    translated_lines: list[str],
    voices: list[str],
    rate_override: str | None = None,
) -> tuple[Path, list[ClipManifest]]:
    video_duration_ms = ffprobe_duration_ms(video_path)
    mix = AudioSegment.silent(duration=video_duration_ms + 800)
    tts_dir = TEMP_DIR / "tts_clips"
    manifest: list[ClipManifest] = []

    active_voices = voices or DEFAULT_VOICES
    for index, (subtitle, text) in enumerate(zip(vietnamese_subtitles, translated_lines), start=1):
        clean_text = normalize_text(text)
        if not clean_text:
            continue

        start_ms = int(subtitle.start.total_seconds() * 1000)
        end_ms = int(subtitle.end.total_seconds() * 1000)
        target_ms = max(end_ms - start_ms - 80, 700)
        voice = active_voices[(index - 1) % len(active_voices)]
        rate = rate_override if rate_override is not None else estimate_rate(clean_text, target_ms)

        raw_clip = tts_dir / f"line_{index:04d}.mp3"
        fitted_clip = tts_dir / f"line_{index:04d}.wav"
        try:
            actual_voice, actual_rate = synthesize_with_fallback(clean_text, voice, active_voices, rate, raw_clip)
        except Exception as exc:
            print(f"Warning: skipping TTS for line {index}: {exc}")
            continue
        clip_ms = fit_audio_length(raw_clip, fitted_clip, target_ms)

        clip_audio = AudioSegment.from_file(fitted_clip)
        if len(clip_audio) < target_ms:
            clip_audio += AudioSegment.silent(duration=target_ms - len(clip_audio))
            clip_audio.export(fitted_clip, format="wav")

        mix = mix.overlay(clip_audio, position=start_ms)
        manifest.append(
            ClipManifest(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                voice=actual_voice,
                rate=actual_rate,
                original_text=subtitle.content,
                translated_text=clean_text,
                clip_ms=clip_ms,
                target_ms=target_ms,
            )
        )

    dub_audio_path = TEMP_DIR / "dub_voice_track.wav"
    mix.export(dub_audio_path, format="wav")
    return dub_audio_path, manifest


def mix_audio(video_path: Path, dub_audio_path: Path, keep_original_audio: bool) -> Path:
    dub_audio = AudioSegment.from_file(dub_audio_path) + 2
    target_duration = ffprobe_duration_ms(video_path)
    if len(dub_audio) < target_duration:
        dub_audio += AudioSegment.silent(duration=target_duration - len(dub_audio))

    if not keep_original_audio:
        mixed = dub_audio[:target_duration]
    else:
        original_audio = AudioSegment.from_file(video_path)
        if len(original_audio) < target_duration:
            original_audio += AudioSegment.silent(duration=target_duration - len(original_audio))
        mixed = (original_audio[:target_duration] - 22).overlay(dub_audio[:target_duration])

    mixed_audio_path = TEMP_DIR / "mixed_audio.wav"
    mixed.export(mixed_audio_path, format="wav")
    return mixed_audio_path
