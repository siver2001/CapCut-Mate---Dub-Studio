from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import threading

from .common import *
from .analysis import (
    is_valtec_reference_voice,
    is_valtec_voice_preset,
    is_vieneu_voice_preset,
    resolve_edge_voice_name,
    resolve_tts_output_extension,
    resolve_valtec_prompt_audio,
    resolve_valtec_reference_audio,
    resolve_voice_preset,
    should_use_valtec_voice,
    should_use_vieneu_voice,
)
from .runtime import (
    ensure_edge_tts_runtime,
    ensure_source_separation_runtime,
    ensure_valtec_runtime,
    temporarily_disable_dead_local_proxies,
    temporarily_use_workspace_torch_home,
)
from ..tts.cache import build_tts_cache_paths
from ..tts.resilience import (
    TtsRateLimiter,
    is_edge_drm_error as _tts_is_edge_drm_error,
    is_edge_no_audio_error as _tts_is_edge_no_audio_error,
    retry_sleep_seconds,
    should_retry_edge_tts_with_cli as _tts_should_retry_edge_tts_with_cli,
)
from ..tts.text import (
    build_edge_tts_safe_rewrites as _tts_build_edge_tts_safe_rewrites,
    ensure_edge_tts_terminal_punctuation as _tts_ensure_edge_tts_terminal_punctuation,
    normalize_edge_tts_text as _tts_normalize_edge_tts_text,
    sanitize_edge_tts_text as _tts_sanitize_edge_tts_text,
    sanitize_for_tts_or_raise,
    strip_trailing_vietnamese_filler as _tts_strip_trailing_vietnamese_filler,
)
from ..tts.voices import (
    EDGE_VOICE_HEALTH,
    preflight_edge_voice,
    resolve_edge_voice_candidates as _tts_resolve_edge_voice_candidates,
)


def clamp_background_music_volume(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 2.0))
    except Exception:
        return 0.0


def append_looped_background_music_input(
    command: list[str],
    filter_parts: list[str],
    *,
    background_music_path: Path | None,
    background_music_volume: float,
    target_duration_ms: int,
    input_index: int,
    label: str = "bgm",
) -> tuple[int, str | None]:
    resolved_path = Path(background_music_path).expanduser() if background_music_path else None
    safe_volume = clamp_background_music_volume(background_music_volume)
    if (
        resolved_path is None
        or safe_volume <= 0.0
        or target_duration_ms <= 0
        or not resolved_path.exists()
        or not resolved_path.is_file()
    ):
        return input_index, None
    command.extend(["-stream_loop", "-1", "-i", str(resolved_path)])
    filter_parts.append(
        f"[{input_index}:a]atrim=0:{max(target_duration_ms, 200) / 1000:.3f},"
        f"asetpts=N/SR/TB,volume={safe_volume:.3f}[{label}]"
    )
    return input_index + 1, f"[{label}]"

def extract_video_clip(video_path: Path, output_path: Path, start_ms: int, duration_ms: int) -> None:
    from .render import choose_video_codec

    codec, codec_args = choose_video_codec()
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{max(start_ms, 0) / 1000:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{max(duration_ms, 400) / 1000:.3f}",
            "-c:v",
            codec,
            *codec_args,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ],
        timeout=120.0
    )


def create_intro_audio(
    *,
    video_clip_path: Path,
    intro_voice_path: Path,
    output_path: Path,
    has_audio: bool,
    use_background_audio: bool,
    background_volume: float,
    background_music_path: Path | None = None,
    background_music_volume: float = 0.0,
) -> None:
    background_bed_path: Path | None = None
    if has_audio and use_background_audio:
        try:
            background_bed_path = separate_background_audio(
                video_path=video_clip_path,
                output_dir=output_path.parent / "intro_background",
                phase="render",
                progress=0.875,
            )
        except Exception:
            background_bed_path = None
    wants_background_bed = bool(background_bed_path and background_bed_path.exists())
    wants_background_music = (
        background_music_path is not None
        and Path(background_music_path).expanduser().exists()
        and clamp_background_music_volume(background_music_volume) > 0.0
    )
    if not wants_background_bed and not wants_background_music:
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(intro_voice_path),
                "-af",
                stable_audio_filter_chain(),
                "-ac",
                str(STABLE_AUDIO_CHANNELS),
                "-ar",
                str(STABLE_AUDIO_SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            timeout=60.0,
        )
        return
    target_duration_ms = 0
    try:
        target_duration_ms = max(
            ffprobe_duration_ms(video_clip_path),
            ffprobe_audio_duration_ms(intro_voice_path),
        )
    except Exception:
        target_duration_ms = ffprobe_audio_duration_ms(intro_voice_path)
    command = ["ffmpeg", "-y"]
    filter_parts: list[str] = []
    mix_inputs: list[str] = []
    input_index = 0
    if wants_background_bed:
        command.extend(["-i", str(background_bed_path)])
        filter_parts.append(
            f"[{input_index}:a]volume={max(min(background_volume, 0.3), 0.0):.3f}[bed]"
        )
        mix_inputs.append("[bed]")
        input_index += 1
    command.extend(["-i", str(intro_voice_path)])
    mix_inputs.append(f"[{input_index}:a]")
    input_index += 1
    input_index, background_music_label = append_looped_background_music_input(
        command,
        filter_parts,
        background_music_path=background_music_path,
        background_music_volume=background_music_volume,
        target_duration_ms=target_duration_ms,
        input_index=input_index,
        label="intro_bgm",
    )
    if background_music_label:
        mix_inputs.append(background_music_label)
    if len(mix_inputs) == 1:
        filter_parts.append(f"{mix_inputs[0]}anull[mix]")
    else:
        filter_parts.append(
            "".join(mix_inputs)
            + f"amix=inputs={len(mix_inputs)}:normalize=0:duration=longest:dropout_transition=0[mix]"
        )
    filter_parts.append(f"[mix]{stable_audio_filter_chain()}[aout]")
    run(
        [
            *command,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[aout]",
            "-ac",
            str(STABLE_AUDIO_CHANNELS),
            "-ar",
            str(STABLE_AUDIO_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        timeout=120.0
    )


def estimate_tts_text_profile(text: str) -> dict[str, float]:
    clean = normalize_text(text)
    words = [part for part in clean.split(" ") if part]
    compact = clean.replace(" ", "")
    chars = len(compact)
    commas = len(re.findall(r"[,;:]", clean))
    hard_pauses = len(re.findall(r"[.!?…]", clean))
    digits = sum(1 for char in clean if char.isdigit())
    uppercase_runs = len(re.findall(r"[A-Z]{2,}", clean))
    spoken_units = (
        chars
        + commas * 2.2
        + hard_pauses * 3.1
        + digits * 0.8
        + uppercase_runs * 1.8
    )
    expected_seconds = max(
        len(words) / 2.35 if words else 0.0,
        spoken_units / 9.8 if spoken_units else 0.0,
        0.82 if chars <= 16 else 1.05,
    )
    return {
        "chars": float(chars),
        "words": float(len(words)),
        "spokenUnits": float(max(spoken_units, 8.0)),
        "expectedSeconds": float(expected_seconds),
    }


def build_tts_delivery_profile(
    *,
    text: str,
    source_text: str,
    voice: str,
    delivery: str,
    intro: bool = False,
) -> dict[str, str]:
    normalized_delivery = str(delivery or "neutral").strip().lower()
    if normalized_delivery not in {"calm", "neutral", "curious", "excited", "urgent", "suspense"}:
        normalized_delivery = "neutral"
    pitch_hz = 0
    volume_percent = 0
    source = normalize_text(source_text)
    spoken = normalize_text(text)
    if normalized_delivery == "calm":
        pitch_hz -= 2
    elif normalized_delivery == "curious":
        pitch_hz += 6
        volume_percent += 1
    elif normalized_delivery == "excited":
        pitch_hz += 9
        volume_percent += 3
    elif normalized_delivery == "urgent":
        pitch_hz += 7
        volume_percent += 2
    elif normalized_delivery == "suspense":
        pitch_hz -= 3
        volume_percent -= 1
    if source.endswith(("?", "？")):
        pitch_hz += 4
    if source.endswith(("!", "！")):
        volume_percent += 1
    if source.endswith(("…", "...")):
        pitch_hz -= 2
    pitch_hz = max(min(pitch_hz, 14), -18)
    volume_percent = max(min(volume_percent, 6), -4)
    return {
        "text": spoken,
        "pitch": f"{pitch_hz:+d}Hz",
        "volume": f"{volume_percent:+d}%",
        "delivery": normalized_delivery,
    }


def parse_rate_percent(rate: str) -> int:
    match = re.match(r"\s*([+-]?\d+)", str(rate or "").strip())
    if not match:
        return 0
    return int(match.group(1))


def is_ultra_tight_mode(timing_mode: str) -> bool:
    return str(timing_mode or "").strip().lower() == "ultra_tight"


def clamp_rate_percent(percent: int, timing_mode: str = "balanced_natural", *, intro: bool = False) -> int:
    ultra_tight = is_ultra_tight_mode(timing_mode)
    if intro:
        if ultra_tight:
            min_rate, max_rate = (5, 25)
        else:
            min_rate, max_rate = (-6, 18) if timing_mode == "balanced_natural" else (-10, 22)
    else:
        if ultra_tight:
            min_rate, max_rate = (-6, 20)
        else:
            min_rate, max_rate = (-10, 12) if timing_mode == "balanced_natural" else (-14, 16)
    return max(min_rate, min(percent, max_rate))


def format_rate_percent(percent: int, timing_mode: str = "balanced_natural", *, intro: bool = False) -> str:
    return f"{clamp_rate_percent(percent, timing_mode=timing_mode, intro=intro):+d}%"


def estimate_rate(text: str, target_ms: int, timing_mode: str = "balanced_natural") -> str:
    target_ms = max(target_ms, 900)
    target_seconds = target_ms / 1000
    profile = estimate_tts_text_profile(text)
    pressure = profile["expectedSeconds"] / max(target_seconds, 0.1)
    percent = int(round((pressure - 1.0) * (78 if is_ultra_tight_mode(timing_mode) else 62)))
    if target_seconds < 1.35:
        percent += 4 if is_ultra_tight_mode(timing_mode) else 2
    elif target_seconds > 3.1:
        percent -= 1 if is_ultra_tight_mode(timing_mode) else 2
    return format_rate_percent(percent, timing_mode=timing_mode)


def estimate_intro_rate(text: str, target_ms: int, timing_mode: str = "balanced_natural") -> str:
    target_ms = max(target_ms, 2000)
    target_seconds = target_ms / 1000
    profile = estimate_tts_text_profile(text)
    # Give intro slightly more breathing room (lower multiplier)
    pressure = profile["expectedSeconds"] / max(target_seconds, 0.1)
    percent = 12 + int(round((pressure - 1.0) * (90 if is_ultra_tight_mode(timing_mode) else 85)))
    return format_rate_percent(percent, timing_mode=timing_mode, intro=True)


def apply_rate_delta(rate: str, delta_percent: int, timing_mode: str = "balanced_natural", *, intro: bool = False) -> str:
    if not delta_percent:
        return rate
    return format_rate_percent(parse_rate_percent(rate) + int(delta_percent), timing_mode=timing_mode, intro=intro)


def smooth_rate_transition(
    rate: str,
    previous_rate: str | None,
    *,
    timing_mode: str,
    target_ms: int,
    delivery: str,
    intro: bool = False,
) -> str:
    if intro or not previous_rate or is_ultra_tight_mode(timing_mode):
        return rate
    current_percent = parse_rate_percent(rate)
    previous_percent = parse_rate_percent(previous_rate)
    max_delta = 6 if target_ms >= 1700 else 8
    if str(delivery or "").strip().lower() in {"excited", "urgent"}:
        max_delta += 2
    if abs(current_percent - previous_percent) <= 3:
        current_percent = int(round((current_percent * 3 + previous_percent) / 4))
    else:
        current_percent = previous_percent + max(min(current_percent - previous_percent, max_delta), -max_delta)
    return format_rate_percent(current_percent, timing_mode=timing_mode, intro=intro)


def _safe_unlink(path: Path, *, retries: int = 5, delay: float = 0.3) -> None:
    """Delete a file, retrying on Windows file-lock errors (WinError 32)."""
    for i in range(retries):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if i < retries - 1:
                time.sleep(delay * (i + 1))
            # Last attempt: ignore if still locked — the next attempt
            # will use a different temp path anyway.


_EDGE_TTS_MIN_REQUEST_GAP_SECONDS = 0.75
_EDGE_TTS_RATE_LIMITER = TtsRateLimiter(min_gap_seconds=_EDGE_TTS_MIN_REQUEST_GAP_SECONDS)


async def _generate_tts_async(
    text: str,
    voice: str,
    rate: str,
    output_path: Path,
    *,
    pitch: str,
    volume: str,
    use_boundary: bool = True,
) -> None:
    ensure_edge_tts_runtime(phase="render", step="prepare", progress=0.03)
    import edge_tts
    with temporarily_disable_dead_local_proxies():
        # edge-tts v7.2.8: boundary must be "SentenceBoundary" or "WordBoundary"
        # (None is no longer accepted). connect_timeout and receive_timeout
        # replace the old external asyncio.wait_for wrapping for more
        # reliable per-socket-operation control.
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
            boundary="SentenceBoundary" if use_boundary else "WordBoundary",
            connect_timeout=min(EDGE_TTS_TIMEOUT, 15),
            receive_timeout=EDGE_TTS_TIMEOUT,
        )
        await asyncio.wait_for(communicate.save(str(output_path)), timeout=EDGE_TTS_TIMEOUT + 10)


def _save_edge_tts_audio(
    text: str,
    voice: str,
    rate: str,
    output_path: Path,
    *,
    pitch: str,
    volume: str,
    use_boundary: bool,
) -> None:
    requested_text = ensure_edge_tts_terminal_punctuation(_normalize_edge_tts_text(text, preserve_pauses=True))
    request_text = sanitize_for_tts_or_raise(
        text,
        speaker_id=f"edge voice {voice}",
    )
    if requested_text and request_text != requested_text:
        safe_print(f"[tts] repaired unsafe low-level Edge text for {voice}.", flush=True)

    def _request() -> None:
        try:
            last_exc = None
            for inner_attempt in range(3):
                try:
                    asyncio.run(
                        _generate_tts_async(
                            request_text,
                            voice,
                            rate,
                            output_path,
                            pitch=pitch,
                            volume=volume,
                            use_boundary=use_boundary,
                        )
                    )
                    return  # Success
                except Exception as exc:
                    last_exc = exc
                    _safe_unlink(output_path)
                    if inner_attempt < 2:
                        time.sleep(2.0 * (inner_attempt + 1))
                    
            if last_exc is not None:
                if not _should_retry_edge_tts_with_cli(last_exc):
                    raise last_exc
                safe_print(
                    "Edge TTS library call returned no audio; retrying once in a fresh edge-tts CLI process.",
                    flush=True,
                )
                _save_edge_tts_audio_with_cli(
                    request_text,
                    voice,
                    rate,
                    output_path,
                    pitch=pitch,
                    volume=volume,
                )
        finally:
            pass

    _EDGE_TTS_RATE_LIMITER.run(_request)


def _should_retry_edge_tts_with_cli(error: Exception) -> bool:
    return _tts_should_retry_edge_tts_with_cli(error)


def _save_edge_tts_audio_with_cli(
    text: str,
    voice: str,
    rate: str,
    output_path: Path,
    *,
    pitch: str,
    volume: str,
) -> None:
    input_fd, input_name = tempfile.mkstemp(
        prefix="edge_tts_input_",
        suffix=".txt",
        dir=str(output_path.parent),
    )
    os.close(input_fd)
    input_path = Path(input_name)
    try:
        input_path.write_text(text, encoding="utf-8")
        with temporarily_disable_dead_local_proxies():
            command = [
                sys.executable,
                "-m",
                "edge_tts",
                f"--voice={voice}",
                f"--file={input_path}",
                f"--rate={rate}",
                f"--volume={volume}",
                f"--pitch={pitch}",
                f"--write-media={output_path}",
            ]
            try:
                run(
                    command,
                    cwd=ROOT,
                    timeout=EDGE_TTS_TIMEOUT + 20,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as exc:
                detail = normalize_text(exc.stderr or exc.stdout or str(exc))
                if "No audio was received" in detail:
                    raise RuntimeError(f"edge-tts CLI returned no audio for {voice}") from exc
                raise RuntimeError(f"edge-tts CLI failed for {voice}: {detail[:300]}") from exc
    finally:
        _safe_unlink(input_path)


def warm_up_edge_tts(voice: str = "vi-VN-NamMinhNeural") -> bool:
    """Make a warm-up TTS call to prime Edge TTS service. Returns True on success."""
    tmp_dir = Path(tempfile.gettempdir())
    warm_up_path = tmp_dir / f"edge_tts_warmup_{threading.get_ident()}.mp3"
    for attempt in range(5):
        try:
            _save_edge_tts_audio(
                text="Xin chao.",
                voice=voice,
                rate="+0%",
                output_path=warm_up_path,
                pitch="+0Hz",
                volume="+0%",
                use_boundary=False,
            )
            _safe_unlink(warm_up_path)
            return True
        except Exception as exc:
            if attempt < 4:
                safe_print(
                    f"Edge TTS warm-up that bai (lan {attempt + 2}/5), cho {3.0 * (attempt + 1):.0f}s roi thu lai...",
                    flush=True,
                )
                time.sleep(3.0 * (attempt + 1))
            else:
                safe_print(
                    f"Edge TTS warm-up that bai sau 5 lan: {exc}. Tiep tuc tao TTS binh thuong.",
                    flush=True,
                )
    return False


def _ffmpeg_audio_codec_args_for_path(output_path: Path) -> list[str]:
    suffix = output_path.suffix.lower()
    if suffix == ".wav":
        return ["-c:a", "pcm_s16le"]
    if suffix in {".m4a", ".aac"}:
        return ["-c:a", "aac", "-b:a", "192k"]
    return ["-c:a", "libmp3lame", "-b:a", "192k"]


def split_edge_tts_text_for_retry(text: str, *, max_chunk_chars: int = 64) -> list[str]:
    clean = ensure_edge_tts_terminal_punctuation(normalize_text(text))
    if not clean:
        return []
    parts = [
        normalize_text(part)
        for part in re.split(r"(?<=[.!?…])\s+|(?<=,)\s+", clean)
        if normalize_text(part)
    ]
    if len(parts) <= 1 and len(clean) <= max_chunk_chars:
        return [clean]

    chunks: list[str] = []
    current = ""
    for part in parts or [clean]:
        candidate = normalize_text(f"{current} {part}" if current else part)
        if current and len(candidate) > max_chunk_chars:
            chunks.append(ensure_edge_tts_terminal_punctuation(current))
            current = part
        else:
            current = candidate
    if current:
        chunks.append(ensure_edge_tts_terminal_punctuation(current))

    final_chunks: list[str] = []
    for chunk in chunks or [clean]:
        if len(chunk) <= max_chunk_chars:
            final_chunks.append(chunk)
            continue
        words = chunk.split()
        current_words: list[str] = []
        for word in words:
            candidate = " ".join([*current_words, word]).strip()
            if current_words and len(candidate) >= max_chunk_chars:
                final_chunks.append(
                    ensure_edge_tts_terminal_punctuation(" ".join(current_words))
                )
                current_words = [word]
            else:
                current_words.append(word)
        if current_words:
            final_chunks.append(
                ensure_edge_tts_terminal_punctuation(" ".join(current_words))
            )

    return [chunk for chunk in final_chunks if chunk]


def synthesize_edge_tts_chunked(
    text: str,
    *,
    edge_voice: str,
    rate: str,
    output_path: Path,
    pitch: str,
    volume: str,
) -> bool:
    last_error: Exception | None = None
    for max_chunk_chars in (64, 48, 32):
        chunks = split_edge_tts_text_for_retry(text, max_chunk_chars=max_chunk_chars)
        if len(chunks) <= 1:
            continue

        temp_parts: list[Path] = []
        concat_list_path: Path | None = None
        try:
            for index, chunk in enumerate(chunks, start=1):
                if index > 1:
                    time.sleep(0.8)
                part_path = output_path.with_name(
                    f"{output_path.stem}.chunk{index:02d}{output_path.suffix}"
                )
                _safe_unlink(part_path)
                _save_edge_tts_audio(
                    chunk,
                    edge_voice,
                    rate,
                    part_path,
                    pitch=pitch,
                    volume=volume,
                    use_boundary=False,
                )
                validate_generated_audio_file(part_path, context=f"Edge TTS chunk {index}")
                temp_parts.append(part_path)

            concat_list_fd, concat_list_name = tempfile.mkstemp(
                prefix="edge_tts_concat_",
                suffix=".txt",
                dir=str(output_path.parent),
            )
            os.close(concat_list_fd)
            concat_list_path = Path(concat_list_name)
            concat_list_path.write_text(
                "\n".join(f"file '{part.name}'" for part in temp_parts),
                encoding="utf-8",
            )
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_list_path),
                    *_ffmpeg_audio_codec_args_for_path(output_path),
                    str(output_path.resolve()),
                ],
                cwd=output_path.parent,
                timeout=90.0,
            )
            validate_generated_audio_file(output_path, context="Edge TTS chunk merge")
            return True
        except Exception as exc:
            last_error = exc
            _safe_unlink(output_path)
            time.sleep(2.5)
        finally:
            if concat_list_path is not None:
                concat_list_path.unlink(missing_ok=True)
            for part in temp_parts:
                _safe_unlink(part)

    if last_error is not None:
        raise last_error
    return False


def _normalize_edge_tts_text(text: str, *, preserve_pauses: bool) -> str:
    return _tts_normalize_edge_tts_text(text, preserve_pauses=preserve_pauses)


def sanitize_edge_tts_text(text: str) -> str:
    return _tts_sanitize_edge_tts_text(text)


def ensure_edge_tts_terminal_punctuation(text: str) -> str:
    return _tts_ensure_edge_tts_terminal_punctuation(text)


def strip_trailing_vietnamese_filler(text: str) -> str:
    return _tts_strip_trailing_vietnamese_filler(text)


def build_edge_tts_safe_rewrites(text: str) -> list[str]:
    return _tts_build_edge_tts_safe_rewrites(text)


def edge_tts_output_looks_hallucinated(text: str, clip_ms: int) -> bool:
    clean = normalize_text(text)
    if not clean:
        return False
    profile = estimate_tts_text_profile(clean)
    expected_ms = max(int(profile["expectedSeconds"] * 1000), 520)
    words = int(profile["words"])
    chars = int(profile["chars"])
    if words <= 3:
        return clip_ms > max(int(expected_ms * 2.15), expected_ms + 1400)
    if words <= 8 or chars <= 42:
        return clip_ms > max(int(expected_ms * 1.75), expected_ms + 1600)
    return clip_ms > max(int(expected_ms * 1.60), expected_ms + 2000)


def resolve_edge_voice_candidates(candidate: str) -> list[str]:
    return _tts_resolve_edge_voice_candidates(candidate)


def is_edge_no_audio_error(error: Exception | str) -> bool:
    return _tts_is_edge_no_audio_error(error)


def is_edge_drm_error(error: Exception | str) -> bool:
    return _tts_is_edge_drm_error(error)


def synthesize_tts(
    text: str,
    voice: str,
    rate: str,
    output_path: Path,
    *,
    pitch: str = "+0Hz",
    volume: str = "+0%",
    speaker_id: str = "speaker_1",
    job_id: str = "",
    global_speed: float = 1.0,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size <= 0:
        output_path.unlink(missing_ok=True)
    selected_voice = resolve_voice_preset(voice)
    
    # Clean text early for all TTS engines (ensures NFC, removes weird chars, adds punctuation)
    edge_text = sanitize_for_tts_or_raise(text, speaker_id=speaker_id)
    
    valtec_prompt_audio = resolve_valtec_prompt_audio(
        speaker_id=speaker_id,
        job_id=job_id,
    )
    valtec_reference_audio = resolve_valtec_reference_audio(selected_voice)

    if is_valtec_voice_preset(selected_voice):
        try:
            from tools.valtec_wrapper import get_valtec_provider
            
            import unicodedata, re
            clean_valtec_text = unicodedata.normalize("NFC", str(edge_text).strip())
            clean_valtec_text = re.sub(r"\.{2,}", ".", clean_valtec_text)
            clean_valtec_text = re.sub(r"\s+", " ", clean_valtec_text)
            if clean_valtec_text and not clean_valtec_text[-1] in (".", "!", "?", ",", ";", ":"):
                clean_valtec_text += "."

            # Convert Edge rate (+0%, -10%, etc) to speed factor (length_scale) for Valtec
            speed_val = 1.0
            try:
                if rate and rate.endswith("%"):
                    speed_factor = 1.0 + (float(rate[:-1]) / 100.0)
                    speed_val = 1.0 / max(0.4, speed_factor)
                
                # Apply global speed adjustment (e.g. 0.9 for slower, 1.1 for faster)
                if global_speed != 1.0:
                    speed_val = speed_val / max(0.1, global_speed)
                    
                speed_val = max(0.4, min(2.5, speed_val))
            except Exception:
                speed_val = 1.0

            provider = get_valtec_provider()
            success = provider.synthesize(
                text=clean_valtec_text,
                output_path=output_path,
                voice_name=selected_voice,
                prompt_audio=valtec_prompt_audio or valtec_reference_audio,
                speed=speed_val
            )
            if success:
                validate_generated_audio_file(output_path, context="Valtec-TTS synthesis")
                return
        except Exception as e:
            raise RuntimeError(
                f"Valtec-TTS synthesis failed for {speaker_id} with voice {selected_voice}: {e}"
            ) from e
        raise RuntimeError(
            f"Valtec-TTS did not create audio for {speaker_id} with voice {selected_voice}."
        )

    if is_vieneu_voice_preset(selected_voice):
        try:
            import unicodedata, re
            clean_vieneu_text = unicodedata.normalize("NFC", str(edge_text).strip())
            clean_vieneu_text = re.sub(r"\.{2,}", ".", clean_vieneu_text)
            clean_vieneu_text = re.sub(r"\s+", " ", clean_vieneu_text)
            if clean_vieneu_text and not clean_vieneu_text[-1] in (".", "!", "?", ",", ";", ":"):
                clean_vieneu_text += "."

            from tools.vieneu_wrapper import get_vieneu_provider
            provider = get_vieneu_provider()
            success = provider.synthesize(
                text=clean_vieneu_text,
                output_path=output_path,
                voice_name=selected_voice,
            )
            if success:
                validate_generated_audio_file(output_path, context="VieNeu-TTS synthesis")
                return
        except Exception as e:
            raise RuntimeError(
                f"VieNeu-TTS synthesis failed for {speaker_id} with voice {selected_voice}: {e}"
            ) from e
        raise RuntimeError(
            f"VieNeu-TTS did not create audio for {speaker_id} with voice {selected_voice}."
        )

    requested_edge_text = ensure_edge_tts_terminal_punctuation(_normalize_edge_tts_text(text, preserve_pauses=True))
    if requested_edge_text and edge_text != requested_edge_text:
        safe_print(
            f"[tts] repaired unsafe text for {speaker_id} before Edge TTS.",
            flush=True,
        )
    sanitized_edge_text = ensure_edge_tts_terminal_punctuation(sanitize_edge_tts_text(text))
    stripped_filler_text = ensure_edge_tts_terminal_punctuation(strip_trailing_vietnamese_filler(edge_text))
    if not edge_text:
        raise RuntimeError("Edge TTS synthesis skipped because spoken text is empty after cleanup.")

    last_error = "unknown error"
    edge_voice_candidates = resolve_edge_voice_candidates(selected_voice)

    for voice_index, edge_voice in enumerate(edge_voice_candidates):
        if EDGE_VOICE_HEALTH.is_unhealthy(edge_voice):
            last_error = f"Edge voice {edge_voice} is in cooldown after repeated no-audio responses."
            continue
        for attempt in range(4):  # Increased to 4 attempts for more fallback options
            current_text = edge_text
            current_use_boundary = True

            # Fallback strategies
            if attempt == 1:
                # Attempt 2: retry with the same text but without boundary metadata.
                current_use_boundary = False
            elif attempt == 2:
                # Attempt 3: drop only the trailing filler / extra polish, keep pauses.
                current_text = stripped_filler_text or edge_text
                current_use_boundary = False
            elif attempt == 3:
                # Attempt 4: last resort with the sanitized variant and neutral params.
                current_text = sanitized_edge_text or edge_text
                current_use_boundary = False

            # Use a unique temp path per attempt to avoid WinError 32
            # (file still locked by a previous asyncio.run / edge-tts websocket).
            temp_output_path = output_path.with_name(
                f"{output_path.stem}.tmp{attempt}{output_path.suffix}"
            )
            _safe_unlink(temp_output_path)

            try:
                _save_edge_tts_audio(
                    current_text,
                    edge_voice,
                    rate if attempt < 3 else "+0%",
                    temp_output_path,
                    pitch=pitch if attempt < 3 else "+0Hz",
                    volume=volume if attempt < 3 else "+0%",
                    use_boundary=current_use_boundary,
                )
                validate_generated_audio_file(temp_output_path, context="Edge TTS synthesis")
                clip_ms = ffprobe_audio_duration_ms(temp_output_path)
                if edge_tts_output_looks_hallucinated(current_text, clip_ms):
                    raise RuntimeError(
                        f"Edge TTS output looks hallucinated ({clip_ms}ms for {len(current_text.split())} words)"
                    )
                EDGE_VOICE_HEALTH.mark_healthy(edge_voice)
                temp_output_path.replace(output_path)
                return
            except Exception as exc:
                last_error = str(exc)
                _safe_unlink(temp_output_path)
                no_audio_error = is_edge_no_audio_error(exc)
                drm_error = is_edge_drm_error(exc)
                if no_audio_error:
                    EDGE_VOICE_HEALTH.mark_transient_failure(edge_voice)

                # edge-tts v7.2.x: DRM 403 errors may self-correct after
                # the library adjusts clock skew internally.  A short pause
                # and retry is the recommended approach.
                if drm_error and attempt < 3:
                    safe_print(
                        f"Edge TTS DRM/403 error (attempt {attempt + 1}/4), Microsoft đang chặn IP hoặc clock skew; "
                        f"thực hiện hard sleep 12s và kích hoạt adaptive backoff...",
                        flush=True,
                    )
                    _EDGE_TTS_RATE_LIMITER.trigger_backoff(duration=180.0)
                    time.sleep(12.0)
                    continue
                if no_audio_error and attempt >= 1:
                    try:
                        if synthesize_edge_tts_chunked(
                            current_text,
                            edge_voice=edge_voice,
                            rate=rate if attempt < 3 else "+0%",
                            output_path=temp_output_path,
                            pitch=pitch if attempt < 3 else "+0Hz",
                            volume=volume if attempt < 3 else "+0%",
                        ):
                            temp_output_path.replace(output_path)
                            return
                    except Exception as chunk_exc:
                        last_error = f"{last_error} | chunked_retry={chunk_exc}"
                if no_audio_error and EDGE_VOICE_HEALTH.transient_failure_count(edge_voice) >= 20:
                    safe_print(
                        f"Edge TTS voice {edge_voice} đang bị cooldown do trả về rỗng liên tiếp quá nhiều lần; "
                        f"kích hoạt global backoff 2 phút cho toàn bộ dịch vụ Edge.",
                        flush=True,
                    )
                    _EDGE_TTS_RATE_LIMITER.trigger_backoff(duration=120.0)
                    break
                if attempt < 3 and not (no_audio_error and attempt >= 1):
                    safe_print(
                        f"Edge TTS retry {attempt + 2}/4 for voice {edge_voice}: {last_error} (Text length: {len(current_text)})"
                    )
                    time.sleep(retry_sleep_seconds(attempt))
                    continue
                if no_audio_error and attempt >= 1:
                    safe_print(
                        f"Edge TTS voice {edge_voice} trả về rỗng cho {speaker_id}, thử lại bằng cách chia câu nhưng vẫn giữ nguyên voice.",
                        flush=True,
                    )
                    if attempt < 3:
                        time.sleep(retry_sleep_seconds(attempt, no_audio=True))
                        continue
                    break

        if voice_index + 1 < len(edge_voice_candidates):
            safe_print(
                f"Edge TTS voice fallback: {edge_voice} failed for {speaker_id}, trying {edge_voice_candidates[voice_index + 1]}",
                flush=True,
            )
            time.sleep(3.5)

    text_snippet = (text[:60] + "...") if len(text) > 60 else text
    raise RuntimeError(
        f"Edge TTS synthesis failed for {speaker_id} (text: \"{text_snippet}\") "
        f"after trying voices {', '.join(edge_voice_candidates)}: {last_error}"
    )


def build_atempo_filter(speed_factor: float) -> str:
    factor = max(speed_factor, 0.1)
    if 0.5 <= factor <= 2.0:
        return f"atempo={factor:.4f}"
    if factor < 0.5:
        parts = []
        current = factor
        while current < 0.5:
            parts.append("atempo=0.5")
            current /= 0.5
        if current != 1.0:
            parts.append(f"atempo={current:.4f}")
        return ",".join(parts)
    else:
        parts = []
        current = factor
        while current > 2.0:
            parts.append("atempo=2.0")
            current /= 2.0
        if current != 1.0:
            parts.append(f"atempo={current:.4f}")
        return ",".join(parts)


def fit_audio_length(source_path: Path, output_path: Path, target_ms: int) -> int:
    return fit_audio_length_with_mode(source_path, output_path, target_ms, timing_mode="balanced_natural")


def fit_audio_length_with_mode(
    source_path: Path,
    output_path: Path,
    target_ms: int,
    timing_mode: str,
    *,
    preserve_voice: bool = False,
) -> int:
    clip_ms = ffprobe_audio_duration_ms(source_path)
    ultra_tight = is_ultra_tight_mode(timing_mode)
    target_fill_ms = max(int(target_ms * (0.996 if ultra_tight else 0.985)), 700)
    # Deadzone: if the duration is already within 1.5% of the target, 
    # skip atempo to avoid unnecessary audio degradation.
    if abs(clip_ms - target_fill_ms) <= (42 if ultra_tight else 95):
        run(["ffmpeg", "-y", "-i", str(source_path), str(output_path)], timeout=60.0)
        return ffprobe_audio_duration_ms(output_path)

    if preserve_voice:
        ratio = clip_ms / max(target_fill_ms, 1)
        # Allow subtle time-stretching (within 8%) even for high-fidelity voices
        # as it sounds more natural than silence padding or abrupt truncation.
        if 0.92 <= ratio <= 1.08:
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source_path),
                    "-filter:a",
                    build_atempo_filter(ratio),
                    str(output_path),
                ]
            )
            return ffprobe_audio_duration_ms(output_path)
            
        if clip_ms < target_fill_ms:
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source_path),
                    "-af",
                    f"apad=pad_dur={max((target_fill_ms - clip_ms) / 1000, 0.1):.3f}",
                    "-t",
                    f"{target_fill_ms / 1000:.3f}",
                    str(output_path),
                ]
            )
        else:
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source_path),
                    "-t",
                    f"{target_ms / 1000:.3f}",
                    str(output_path),
                ]
            )
        return ffprobe_audio_duration_ms(output_path)

    if clip_ms < target_fill_ms:
        stretch_ratio = target_fill_ms / max(clip_ms, 1)
        if stretch_ratio <= (1.08 if ultra_tight else 1.12):
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
        else:
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source_path),
                    "-af",
                    f"apad=pad_dur={max((target_fill_ms - clip_ms) / 1000, 0.1):.3f}",
                    "-t",
                    f"{target_fill_ms / 1000:.3f}",
                    str(output_path),
                ]
            )
        return ffprobe_audio_duration_ms(output_path)

    speed_factor = clip_ms / max(target_fill_ms, 1)
    # Prevent excessive time-stretching that degrades natural vocal cadence ("bắn liên thanh")
    max_allowed_speed = 1.20 if ultra_tight else 1.15
    if speed_factor > max_allowed_speed:
        speed_factor = max_allowed_speed

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
    fitted_ms = ffprobe_audio_duration_ms(output_path)
    if fitted_ms > target_ms:
        trimmed_output = output_path.with_name(f"{output_path.stem}_trimmed{output_path.suffix}")
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(output_path),
                "-t",
                f"{target_ms / 1000:.3f}",
                str(trimmed_output),
            ]
        )
        trimmed_output.replace(output_path)
        fitted_ms = ffprobe_audio_duration_ms(output_path)
    return fitted_ms


def fit_intro_audio_length(source_path: Path, output_path: Path, target_ms: int) -> int:
    clip_ms = ffprobe_audio_duration_ms(source_path)
    target_fill_ms = max(int(target_ms), 900)
    if clip_ms <= target_fill_ms:
        run(["ffmpeg", "-y", "-i", str(source_path), str(output_path)], timeout=60.0)
        return clip_ms
    return fit_audio_length(source_path, output_path, target_fill_ms)


def measure_audio_rms_db(path: Path) -> float | None:
    try:
        import librosa
        import numpy as np

        audio, _ = librosa.load(str(path), sr=16000, mono=True)
        if audio.size == 0:
            return None
        rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
        return 20.0 * math.log10(max(rms, 1e-6))
    except Exception:
        return None


def compute_energy_match_gain_db(reference_path: Path, dub_path: Path, *, max_gain_db: float) -> tuple[float, float | None, float | None]:
    reference_db = measure_audio_rms_db(reference_path)
    dub_db = measure_audio_rms_db(dub_path)
    if reference_db is None or dub_db is None:
        return 0.0, reference_db, dub_db
    gain_db = max(min(reference_db - dub_db, max_gain_db), -max_gain_db)
    return gain_db, reference_db, dub_db


def resolve_segment_target_ms(
    segments: list[dict[str, Any]],
    index: int,
    *,
    video_duration_ms: int,
    timing_mode: str = "balanced_natural",
    text: str = "",
) -> int:
    segment = segments[index]
    start_ms = max(int(segment.get("startMs", 0)), 0)
    end_ms = max(int(segment.get("endMs", start_ms + 700)), start_ms + 200)
    base_duration = max(end_ms - start_ms, 420)
    previous_end = max(int(segments[index - 1].get("endMs", 0)), 0) if index > 0 else 0
    next_start = (
        max(int(segments[index + 1].get("startMs", end_ms)), end_ms)
        if index + 1 < len(segments)
        else max(int(video_duration_ms), end_ms)
    )
    gap_before = max(start_ms - previous_end, 0)
    gap_after = max(next_start - end_ms, 0)
    ultra_tight = is_ultra_tight_mode(timing_mode)
    lead_guard = min(36 if ultra_tight else 50, gap_before // (4 if ultra_tight else 3))
    tail_allowance = min(int(gap_after * (0.35 if ultra_tight else 0.75)), 300 if ultra_tight else 850)
    target_ms = base_duration - lead_guard - (30 if ultra_tight else 50) + tail_allowance
    max_available = max(next_start - start_ms - (40 if ultra_tight else 70), 520)
    profile = estimate_tts_text_profile(text or segment.get("translatedText") or segment.get("sourceText") or "")
    punctuation_bonus = 80 if normalize_text(text or "").endswith(("?", "!", "...", "…")) else 0
    speech_floor = int(profile["expectedSeconds"] * 1000) + punctuation_bonus
    min_target = 600 if ultra_tight else 620 if base_duration < 1200 else 760
    target_ms = max(int(target_ms), min(speech_floor, int(max_available)))
    # Allow 150ms overlap if speech floor is still higher than max available
    final_limit = max_available + 150
    return max(min(int(target_ms), int(final_limit)), min_target)


def refine_tts_rate(
    current_rate: str,
    *,
    raw_ms: int,
    target_ms: int,
    timing_mode: str,
    intro: bool = False,
) -> str:
    ratio = raw_ms / max(target_ms, 1)
    ultra_tight = is_ultra_tight_mode(timing_mode)
    if (0.96 <= ratio <= 1.06) if ultra_tight else (0.9 <= ratio <= 1.12):
        return current_rate
    adjustment = int(round((ratio - 1.0) * (80 if ultra_tight else 65)))
    if ratio > (1.22 if ultra_tight else 1.35):
        adjustment += 4 if ultra_tight else 2
    elif ratio < (0.84 if ultra_tight else 0.75):
        adjustment -= 4 if ultra_tight else 2
    next_percent = parse_rate_percent(current_rate) + adjustment
    return format_rate_percent(next_percent, timing_mode=timing_mode, intro=intro)


def voice_cache_salt(voice: str) -> str:
    selected_voice = resolve_voice_preset(voice)
    reference_audio = resolve_valtec_reference_audio(selected_voice)
    if reference_audio is None or not reference_audio.exists():
        return ""
    stat = reference_audio.stat()
    return f"{reference_audio.name}:{stat.st_size}:{stat.st_mtime_ns}"


def synthesize_timed_tts_clip(
    *,
    index: int,
    speaker_id: str,
    voice: str,
    translated: str,
    source_text: str = "",
    delivery: str = "neutral",
    target_ms: int,
    timing_mode: str,
    tts_dir: Path,
    intro: bool = False,
    rate_delta_percent: int = 0,
    previous_rate: str | None = None,
    job_id: str = "",
    global_speed: float = 1.0,
) -> tuple[Path, int, str, str, str, str]:
    delivery_profile = build_tts_delivery_profile(
        text=translated,
        source_text=source_text or translated,
        voice=voice,
        delivery=delivery,
        intro=intro,
    )
    tts_text = normalize_text(delivery_profile["text"])
    pitch = delivery_profile["pitch"]
    volume = delivery_profile["volume"]
    rate = estimate_intro_rate(tts_text, target_ms, timing_mode=timing_mode) if intro else estimate_rate(tts_text, target_ms, timing_mode=timing_mode)
    rate = apply_rate_delta(rate, rate_delta_percent, timing_mode=timing_mode, intro=intro)
    rate = smooth_rate_transition(
        rate,
        previous_rate,
        timing_mode=timing_mode,
        target_ms=target_ms,
        delivery=delivery,
        intro=intro,
    )
    best: dict[str, Any] | None = None
    seen_rates: set[str] = set()
    ultra_tight = is_ultra_tight_mode(timing_mode)
    text_candidates = [tts_text]
    terminal_synthesis_error: Exception | None = None
    preserve_valtec_reference_voice = is_valtec_reference_voice(resolve_voice_preset(voice))

    for _ in range(4 if ultra_tight else 3):
        if rate in seen_rates:
            break
        seen_rates.add(rate)
        rate_candidate: dict[str, Any] | None = None
        last_synthesis_error: Exception | None = None
        for candidate_text in text_candidates:
            raw_extension = resolve_tts_output_extension(
                voice=voice,
                speaker_id=speaker_id,
                job_id=job_id,
            )
            cache_paths = build_tts_cache_paths(
                tts_dir=tts_dir,
                index=index,
                speaker_id=speaker_id,
                voice=voice,
                voice_cache_salt=voice_cache_salt(voice),
                rate=rate,
                pitch=pitch,
                volume=volume,
                text=candidate_text,
                raw_extension=raw_extension,
                target_ms=target_ms,
                timing_mode=timing_mode,
                global_speed=global_speed,
            )
            raw_clip = cache_paths.raw_clip
            prepared_clip = cache_paths.prepared_clip
            fitted_clip = cache_paths.fitted_clip
            if raw_clip.exists() and raw_clip.stat().st_size <= 0:
                raw_clip.unlink(missing_ok=True)
            if raw_clip.exists():
                try:
                    cached_raw_ms = ffprobe_audio_duration_ms(raw_clip)
                except Exception:
                    cached_raw_ms = 0
                if cached_raw_ms <= 0 or edge_tts_output_looks_hallucinated(candidate_text, cached_raw_ms):
                    raw_clip.unlink(missing_ok=True)
            if not raw_clip.exists():
                try:
                    synthesize_tts(
                        tts_text,
                        voice,
                        rate,
                        raw_clip,
                        pitch=pitch,
                        volume=volume,
                        speaker_id=speaker_id,
                        job_id=job_id,
                        global_speed=global_speed,
                    )
                except Exception as exc:
                    last_synthesis_error = exc
                    if intro:
                        terminal_synthesis_error = exc
                        break
                    if candidate_text != tts_text:
                        safe_print(
                            f"Falling back to safer TTS text for segment {index}: {exc}",
                            flush=True,
                        )
                    continue
            prepare_tts_clip_for_timeline(raw_clip, prepared_clip)
            raw_ms = ffprobe_audio_duration_ms(prepared_clip)
            cached_fitted_ms = 0
            if TTS_FIT_CACHE_ENABLED and fitted_clip.exists():
                try:
                    cached_fitted_ms = ffprobe_audio_duration_ms(fitted_clip)
                except Exception:
                    cached_fitted_ms = 0
                if cached_fitted_ms <= 0:
                    fitted_clip.unlink(missing_ok=True)
            clip_ms = (
                cached_fitted_ms
                if cached_fitted_ms > 0
                else fit_audio_length_with_mode(
                    prepared_clip,
                    fitted_clip,
                    target_ms,
                    timing_mode,
                    preserve_voice=preserve_valtec_reference_voice,
                )
            )
            fit_error = abs(clip_ms - target_ms)
            pressure_penalty = abs(math.log(max(raw_ms / max(target_ms, 1), 0.001))) * (220 if ultra_tight else 180)
            rate_candidate = {
                "path": fitted_clip,
                "clipMs": clip_ms,
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "text": candidate_text,
                "score": fit_error + pressure_penalty,
                "fitError": fit_error,
                "rawMs": raw_ms,
            }
            break
        if rate_candidate is None:
            terminal_synthesis_error = last_synthesis_error
            break
        candidate = rate_candidate
        if best is None or candidate["score"] < best["score"]:
            best = candidate
        if (
            candidate["fitError"] <= (40 if ultra_tight else 70)
            and ((0.92 <= candidate["rawMs"] / max(target_ms, 1) <= 1.08) if ultra_tight else (0.86 <= candidate["rawMs"] / max(target_ms, 1) <= 1.18))
        ):
            break
        next_rate = refine_tts_rate(
            rate,
            raw_ms=int(candidate["rawMs"]),
            target_ms=target_ms,
            timing_mode=timing_mode,
            intro=intro,
        )
        if next_rate == rate:
            break
        rate = next_rate

    if best is None:
        if intro and terminal_synthesis_error is not None:
            raise terminal_synthesis_error
        direct_fallback_text = ensure_edge_tts_terminal_punctuation(
            normalize_text(translated or tts_text)
        )
        if direct_fallback_text:
            try:
                raw_extension = resolve_tts_output_extension(
                    voice=voice,
                    speaker_id=speaker_id,
                    job_id=job_id,
                    global_speed=global_speed,
                )
                cache_paths = build_tts_cache_paths(
                    tts_dir=tts_dir,
                    index=index,
                    speaker_id=speaker_id,
                    voice=voice,
                    voice_cache_salt=voice_cache_salt(voice),
                    rate="direct",
                    pitch="+0Hz",
                    volume="+0%",
                    text=direct_fallback_text,
                    raw_extension=raw_extension,
                    target_ms=target_ms,
                    timing_mode=timing_mode,
                )
                raw_clip = cache_paths.raw_clip
                prepared_clip = cache_paths.prepared_clip
                fitted_clip = cache_paths.fitted_clip
                synthesize_tts(
                    direct_fallback_text,
                    voice,
                    "+0%",
                    raw_clip,
                    pitch="+0Hz",
                    volume="+0%",
                    speaker_id=speaker_id,
                    job_id=job_id,
                    global_speed=global_speed,
                )
                prepare_tts_clip_for_timeline(raw_clip, prepared_clip)
                clip_ms = fit_audio_length_with_mode(
                    prepared_clip,
                    fitted_clip,
                    target_ms,
                    timing_mode,
                    preserve_voice=preserve_valtec_reference_voice,
                )
                return (
                    fitted_clip,
                    int(clip_ms),
                    "+0%",
                    "+0Hz",
                    "+0%",
                    direct_fallback_text,
                )
            except Exception as exc:
                terminal_synthesis_error = exc
        if terminal_synthesis_error is not None:
            raise terminal_synthesis_error
        raise RuntimeError("Could not synthesize a timed TTS clip.")
    return (
        Path(best["path"]),
        int(best["clipMs"]),
        str(best["rate"]),
        str(best["pitch"]),
        str(best["volume"]),
        str(best["text"]),
    )


def prepare_tts_clip_for_timeline(source_path: Path, output_path: Path) -> Path:
    if output_path.exists() and output_path.stat().st_size > 0:
        try:
            ffprobe_audio_duration_ms(output_path)
            return output_path
        except Exception:
            output_path.unlink(missing_ok=True)
    trim_boundaries = source_path.suffix.lower() in {".mp3", ".aac", ".m4a"}
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-af",
        stable_audio_filter_chain(trim_boundaries=trim_boundaries),
        "-ac",
        str(STABLE_AUDIO_CHANNELS),
        "-ar",
        str(STABLE_AUDIO_SAMPLE_RATE),
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    try:
        run(command, timeout=60.0)
    except Exception:
        if not trim_boundaries:
            raise
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-af",
                stable_audio_filter_chain(),
                "-ac",
                str(STABLE_AUDIO_CHANNELS),
                "-ar",
                str(STABLE_AUDIO_SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            timeout=60.0,
        )
    validate_generated_audio_file(output_path, context="Prepared TTS clip")
    return output_path


def _tts_provider_for_voice(voice: str) -> str:
    selected_voice = resolve_voice_preset(voice)
    if is_vieneu_voice_preset(selected_voice):
        if not DUB_USE_VIENEU:
            raise RuntimeError(
                f"Voice {selected_voice} requires VieNeu-TTS, but DUB_USE_VIENEU is disabled."
            )
        return "vieneu"
    if is_valtec_voice_preset(selected_voice):
        if not DUB_USE_VALTEC:
            raise RuntimeError(
                f"Voice {selected_voice} requires Valtec-TTS, but DUB_USE_VALTEC is disabled."
            )
        return "valtec"
    return "edge"


def _raise_missing_tts_text(segment: dict[str, Any], index: int, field_name: str) -> None:
    segment_id = normalize_text(segment.get("id") or str(index))
    source_text = normalize_text(segment.get("sourceText") or "")
    raise RuntimeError(
        f"Missing {field_name} for TTS segment {segment_id}. "
        "Render stopped instead of creating a silent voice gap. "
        f"Source text: {source_text[:160]}"
    )


def _run_tts_chain(
    *,
    items: list[dict[str, Any]],
    total_segments: int,
    timing_mode: str,
    tts_dir: Path,
    job_id: str,
    global_speed: float = 1.0,
) -> list[dict[str, Any]]:
    chain_results: list[dict[str, Any]] = []

    # Natural Pacing Chaining: Group adjacent segments into 'flow blocks'
    # if they share the same voice/speaker and have minimal gaps.
    flow_blocks: list[list[dict[str, Any]]] = []
    current_block: list[dict[str, Any]] = []

    for item in items:
        if not current_block:
            current_block.append(item)
            continue

        prev = current_block[-1]
        gap = int(item["segment"]["startMs"]) - int(prev["segment"]["endMs"])

        # If segments are very close (< 250ms), treat them as one continuous speech flow
        if 0 <= gap < 250:
            current_block.append(item)
        else:
            flow_blocks.append(current_block)
            current_block = [item]
    if current_block:
        flow_blocks.append(current_block)

    previous_rate: str | None = None

    edge_voices: list[str] = []
    seen_edge_voices: set[str] = set()
    for item in items:
        if item.get("provider") != "edge":
            continue
        for candidate in resolve_edge_voice_candidates(str(item.get("voice") or "vi-VN-NamMinhNeural")):
            if candidate not in seen_edge_voices:
                seen_edge_voices.add(candidate)
                edge_voices.append(candidate)
    for edge_voice in edge_voices:
        preflight_edge_voice(
            edge_voice,
            output_dir=tts_dir / "_preflight",
            save_audio=_save_edge_tts_audio,
            validate_audio=validate_generated_audio_file,
            safe_print=safe_print,
        )

    if edge_voices:
        warm_up_edge_tts(edge_voices[0])

    for block in flow_blocks:
        if not block:
            continue

        # If block has multiple items, we synthesize them as ONE to get natural intonation
        if len(block) > 1:
            combined_text = ". ".join(normalize_text(it["translated"]) for it in block)
            # Add final punctuation if missing
            if not combined_text.endswith((".", "!", "?", "…")):
                combined_text += "."

            first_item = block[0]
            last_item = block[-1]
            total_target_ms = int(last_item["segment"]["endMs"]) - int(first_item["segment"]["startMs"])

            safe_print(f"[tts] Chaining {len(block)} segments for natural pacing (Total: {total_target_ms}ms)", flush=True)

            try:
                fitted_clip, clip_ms, rate, pitch, volume, tts_text = synthesize_timed_tts_clip(
                    index=first_item["index"],
                    speaker_id=first_item["speaker_id"],
                    voice=first_item["voice"],
                    translated=combined_text,
                    source_text=first_item["source_text"],
                    delivery=first_item["delivery"],
                    target_ms=total_target_ms,
                    timing_mode=timing_mode,
                    tts_dir=tts_dir,
                    previous_rate=previous_rate,
                    job_id=job_id,
                    global_speed=global_speed,
                )
                previous_rate = rate

                # The first item gets the combined audio
                chain_results.append({
                    **first_item,
                    "fitted_clip": fitted_clip,
                    "clip_ms": clip_ms,
                    "rate": rate,
                    "pitch": pitch,
                    "volume": volume,
                    "tts_text": tts_text,
                })

                # Subsequent items in the same block are marked as 'chained' with a silent placeholder
                # so they don't trigger redundant synthesis or overlapping audio.
                for idx in range(1, len(block)):
                    sub_item = block[idx]
                    silent_clip = tts_dir / f"{sub_item['index']:04d}_chained_placeholder.wav"
                    if not silent_clip.exists():
                        run(["ffmpeg", "-y", "-f", "lavfi", "-t", "0.01", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000", "-ac", str(STABLE_AUDIO_CHANNELS), "-ar", str(STABLE_AUDIO_SAMPLE_RATE), "-c:a", "pcm_s16le", str(silent_clip)], timeout=15.0)

                    chain_results.append({
                        **sub_item,
                        "fitted_clip": silent_clip,
                        "clip_ms": 10,
                        "rate": rate,
                        "pitch": pitch,
                        "volume": volume,
                        "tts_text": "(chained)",
                    })
                continue
            except Exception as exc:
                safe_print(f"[tts] Chain synthesis failed, falling back to individual processing: {exc}", flush=True)

        # Individual processing for single-item blocks or fallback
        for item in block:
            if item.get("provider") == "edge":
                time.sleep(1.0)

            emit_progress(
                phase="render",
                step="tts",
                progress=0.44 + (item["progress_index"] / max(total_segments, 1)) * 0.16,
                message=(
                    f"Đang tạo lồng tiếng {item['progress_index']}/{total_segments}"
                    f" · {item['speaker_id']} · {item['voice']}"
                ),
            )
            safe_print(
                f"[tts] segment {item['progress_index']}/{total_segments} "
                f"{item['speaker_id']} {item['voice']}",
                flush=True,
            )
            try:
                fitted_clip, clip_ms, rate, pitch, volume, tts_text = synthesize_timed_tts_clip(
                    index=item["index"],
                    speaker_id=item["speaker_id"],
                    voice=item["voice"],
                    translated=item["translated"],
                    source_text=item["source_text"],
                    delivery=item["delivery"],
                    target_ms=item["target_ms"],
                    timing_mode=timing_mode,
                    tts_dir=tts_dir,
                    previous_rate=previous_rate,
                    job_id=job_id,
                    global_speed=global_speed,
                )
            except Exception as exc:
                if not DUB_TTS_ALLOW_SILENT_FALLBACK:
                    raise RuntimeError(
                        f"TTS failed for segment {item['index']} ({item['speaker_id']}), "
                        f"silent fallback is disabled: {exc}"
                    ) from exc
                safe_print(
                    f"  [!] TTS thất bại cho segment {item['index']}: {exc} — tạo clip im thay thế",
                    flush=True,
                )
                target_ms = int(item["target_ms"])
                silent_duration = max(target_ms / 1000.0, 0.05)
                silent_clip = tts_dir / f"{item['index']:04d}_silent_fallback.wav"
                run(
                    [
                        "ffmpeg", "-y",
                        "-f", "lavfi",
                        "-t", f"{silent_duration:.3f}",
                        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-ac", str(STABLE_AUDIO_CHANNELS),
                        "-ar", str(STABLE_AUDIO_SAMPLE_RATE),
                        "-c:a", "pcm_s16le",
                        str(silent_clip),
                    ],
                    timeout=30.0,
                )
                fitted_clip = silent_clip
                clip_ms = int(target_ms)
                rate = "+0%"
                pitch = "+0Hz"
                volume = "+0%"
                tts_text = str(item.get("translated") or "")
            previous_rate = rate
            chain_results.append(
                {
                    **item,
                    "fitted_clip": fitted_clip,
                    "clip_ms": clip_ms,
                    "rate": rate,
                    "pitch": pitch,
                    "volume": volume,
                    "tts_text": tts_text,
                }
            )
    return chain_results



def _create_dub_audio_legacy(
    *,
    job_id: str,
    video_meta: dict[str, Any],
    source_video_path: Path,
    segments: list[dict[str, Any]],
    voices: dict[str, str],
    timing_mode: str,
    tts_dir: Path,
    dub_audio_path: Path,
) -> list[ClipManifest]:
    manifests: list[ClipManifest] = []
    duration_seconds = max(video_meta["durationMs"] / 1000, 0.1)
    tts_inputs: list[str] = []
    filter_parts: list[str] = []
    mix_inputs = ["[0:a]"]
    reference_dir = ensure_dir(tts_dir / "_reference")
    prepared_items: list[dict[str, Any]] = []

    for index, segment in enumerate(segments, start=1):
        translated = normalize_text(segment.get("translatedText") or "")
        if not translated:
            _raise_missing_tts_text(segment, index, "translatedText")
        delivery = normalize_text(segment.get("delivery") or "neutral").lower() or "neutral"
        tts_text = translated
        speaker_id = segment.get("speakerId") or "speaker_1"
        tts_text = sanitize_for_tts_or_raise(
            tts_text,
            speaker_id=f"{segment.get('id') or index}/{speaker_id}",
        )
        voice_override = normalize_text(
            segment.get("voice")
            or segment.get("voicePreset")
            or segment.get("voiceOverride")
            or ""
        )
        voice = voice_override or voices.get(speaker_id) or DEFAULT_VOICES[0]
        emit_progress(
            phase="render",
            step="tts",
            progress=0.44 + progress_ratio * 0.16,
            message=(
                f"Đang tạo lồng tiếng {processed_segments}/{total_segments}"
                f" · {speaker_id} · {voice}"
            ),
        )
        target_ms = resolve_segment_target_ms(
            segments,
            index - 1,
            video_duration_ms=int(video_meta.get("durationMs", 0)),
            timing_mode=timing_mode,
            text=tts_text,
        )
        fitted_clip, clip_ms, rate, pitch, volume, tts_text = synthesize_timed_tts_clip(
            index=index,
            speaker_id=speaker_id,
            voice=voice,
            translated=tts_text,
            source_text=segment.get("sourceText") or translated,
            delivery=delivery,
            target_ms=target_ms,
            timing_mode=timing_mode,
            tts_dir=tts_dir,
            previous_rate=previous_rate_by_speaker.get(speaker_id),
            job_id=job_id,
        )
        previous_rate_by_speaker[speaker_id] = rate

        input_index = len(tts_inputs) // 2 + 1
        tts_inputs.extend(["-i", str(fitted_clip)])
        delay = max(int(segment["startMs"]), 0)
        label = f"d{input_index}"
        energy_gain_db = 0.0
        reference_energy_db: float | None = None
        dub_energy_db: float | None = None
        if DUB_ENABLE_ENERGY_MATCHING:
            reference_clip = reference_dir / f"{segment['id']}_orig.wav"
            try:
                extract_audio_clip(
                    source_video_path,
                    reference_clip,
                    max(int(segment["startMs"]), 0),
                    max(int(segment["endMs"]) - int(segment["startMs"]), 250),
                )
                energy_gain_db, reference_energy_db, dub_energy_db = compute_energy_match_gain_db(
                    reference_clip,
                    fitted_clip,
                    max_gain_db=DUB_MAX_ENERGY_GAIN_DB,
                )
            except Exception:
                energy_gain_db = 0.0
        if abs(energy_gain_db) >= 0.15:
            filter_parts.append(f"[{input_index}:a]volume={energy_gain_db:.2f}dB,adelay={delay}|{delay}[{label}]")
        else:
            filter_parts.append(f"[{input_index}:a]adelay={delay}|{delay}[{label}]")
        mix_inputs.append(f"[{label}]")
        manifests.append(
            ClipManifest(
                index=index,
                segment_id=segment["id"],
                start_ms=int(segment["startMs"]),
                end_ms=int(segment["endMs"]),
                voice=voice,
                rate=rate,
                pitch=pitch,
                volume=volume,
                translated_text=translated,
                delivery=delivery,
                clip_ms=clip_ms,
                target_ms=target_ms,
                fitted_path=str(fitted_clip),
                reference_energy_db=reference_energy_db,
                dub_energy_db=dub_energy_db,
                energy_gain_db=round(energy_gain_db, 3),
            )
        )

    if not manifests:
        run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-t",
                f"{duration_seconds:.3f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-c:a",
                "pcm_s16le",
                str(dub_audio_path),
            ]
        )
        return manifests

    filter_parts.append("".join(mix_inputs) + f"amix=inputs={len(mix_inputs)}:normalize=0:duration=longest:dropout_transition=0[dub]")
    emit_progress(
        phase="render",
        step="tts_mix",
        progress=0.61,
        message="Đang ghép toàn bộ clip lồng tiếng thành một track audio",
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-t",
            f"{duration_seconds:.3f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            *tts_inputs,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[dub]",
            "-c:a",
            "pcm_s16le",
            str(dub_audio_path),
        ]
    )
    return manifests


def create_dub_audio(
    *,
    job_id: str,
    video_meta: dict[str, Any],
    source_video_path: Path,
    segments: list[dict[str, Any]],
    voices: dict[str, str],
    timing_mode: str,
    tts_dir: Path,
    dub_audio_path: Path,
    global_speed: float = 1.0,
) -> list[ClipManifest]:
    manifests: list[ClipManifest] = []
    duration_seconds = max(video_meta["durationMs"] / 1000, 0.1)
    tts_inputs: list[str] = []
    filter_parts: list[str] = []
    mix_inputs = ["[0:a]"]
    reference_dir = ensure_dir(tts_dir / "_reference")
    prepared_items: list[dict[str, Any]] = []
    generated_items: list[dict[str, Any]] = []

    for index, segment in enumerate(segments, start=1):
        translated = normalize_text(segment.get("translatedText") or "")
        delivery = normalize_text(segment.get("delivery") or "neutral").lower() or "neutral"
        speaker_id = segment.get("speakerId") or "speaker_1"
        voice_override = normalize_text(
            segment.get("voice")
            or segment.get("voicePreset")
            or segment.get("voiceOverride")
            or ""
        )
        voice = voice_override or voices.get(speaker_id) or DEFAULT_VOICES[0]
        print(f"DEBUG: Processing segment {index}/{len(segments)}: voice={voice}, text='{translated[:30]}...'", flush=True)

        if not translated:
            target_ms = resolve_segment_target_ms(
                segments,
                index - 1,
                video_duration_ms=int(video_meta.get("durationMs", 0)),
                timing_mode=timing_mode,
                text="",
            )
            silent_duration = max(target_ms / 1000.0, 0.05)
            silent_clip = tts_dir / f"{index:04d}_silent_fallback.wav"
            if not silent_clip.exists() or silent_clip.stat().st_size <= 0:
                run(
                    [
                        "ffmpeg", "-y",
                        "-f", "lavfi",
                        "-t", f"{silent_duration:.3f}",
                        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-ac", str(STABLE_AUDIO_CHANNELS),
                        "-ar", str(STABLE_AUDIO_SAMPLE_RATE),
                        "-c:a", "pcm_s16le",
                        str(silent_clip),
                    ],
                    timeout=30.0,
                )
            generated_items.append(
                {
                    "index": index,
                    "segment": segment,
                    "translated": "",
                    "voice": voice,
                    "delivery": delivery,
                    "target_ms": target_ms,
                    "fitted_clip": silent_clip,
                    "clip_ms": int(target_ms),
                    "rate": "+0%",
                    "pitch": "+0Hz",
                    "volume": "+0%",
                }
            )
            continue

        tts_text = sanitize_for_tts_or_raise(
            translated,
            speaker_id=f"{segment.get('id') or index}/{speaker_id}",
        )
        prepared_items.append(
            {
                "index": index,
                "segment": segment,
                "translated": translated,
                "speaker_id": speaker_id,
                "voice": voice,
                "delivery": delivery,
                "target_ms": resolve_segment_target_ms(
                    segments,
                    index - 1,
                    video_duration_ms=int(video_meta.get("durationMs", 0)),
                    timing_mode=timing_mode,
                    text=tts_text,
                ),
                "source_text": segment.get("sourceText") or translated,
                "provider": _tts_provider_for_voice(voice),
            }
        )

    total_segments = max(len(prepared_items), 1)
    for progress_index, item in enumerate(prepared_items, start=1):
        item["progress_index"] = progress_index

    if prepared_items:
        provider_limits = {
            "edge": EDGE_TTS_CONCURRENCY,
            "vieneu": VIENEU_TTS_CONCURRENCY,
            "valtec": 1,
        }
        for provider in ("edge", "vieneu", "valtec"):
            provider_items = [item for item in prepared_items if item["provider"] == provider]
            if not provider_items:
                continue
            grouped_items: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for item in provider_items:
                chain_key = (str(item["speaker_id"]), str(item["voice"]))
                grouped_items.setdefault(chain_key, []).append(item)
            chains = list(grouped_items.values())
            max_workers = min(provider_limits.get(provider, 1), len(chains))
            if DUB_TTS_ENABLE_PARALLEL and max_workers > 1:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [
                        executor.submit(
                            _run_tts_chain,
                            items=chain,
                            total_segments=total_segments,
                            timing_mode=timing_mode,
                            tts_dir=tts_dir,
                            job_id=job_id,
                            global_speed=global_speed,
                        )
                        for chain in chains
                    ]
                    for future in as_completed(futures):
                        generated_items.extend(future.result())
            else:
                for chain in chains:
                    print(f"DEBUG: Starting _run_tts_chain for {len(chain)} items...", flush=True)
                    generated_items.extend(
                        _run_tts_chain(
                            items=chain,
                            total_segments=total_segments,
                            timing_mode=timing_mode,
                            tts_dir=tts_dir,
                            job_id=job_id,
                            global_speed=global_speed,
                        )
                    )
                    print(f"DEBUG: Finished _run_tts_chain for {len(chain)} items.", flush=True)
    generated_items.sort(key=lambda item: int(item["index"]))

    # Anchor-Sub-Sync pre-pass: Recalculate and synchronize subtitle/audio timing anchors dynamically
    timeline_cursor = 0
    for idx, item in enumerate(generated_items):
        segment = item["segment"]
        clip_ms = int(item["clip_ms"])
        orig_start = max(int(segment.get("startMs", 0)), 0)
        
        # Prevent speech overlaps by forcing sequential start bounds (minimum 50ms interval)
        actual_start = max(orig_start, timeline_cursor)
        if idx > 0:
            prev_end = generated_items[idx - 1]["actual_end"]
            if actual_start < prev_end + 50:
                actual_start = prev_end + 50
                
        actual_end = actual_start + clip_ms
        
        # Save computed timings back to tracking variables and segment dictionary
        item["actual_start"] = actual_start
        item["actual_end"] = actual_end
        segment["startMs"] = actual_start
        segment["endMs"] = actual_end
        
        timeline_cursor = actual_end

    for item in generated_items:
        index = int(item["index"])
        segment = item["segment"]
        translated = str(item["translated"])
        voice = str(item["voice"])
        delivery = str(item["delivery"])
        target_ms = int(item["target_ms"])
        fitted_clip = Path(item["fitted_clip"])
        clip_ms = int(item["clip_ms"])
        rate = str(item["rate"])
        pitch = str(item["pitch"])
        volume = str(item["volume"])
        actual_start = int(item["actual_start"])
        actual_end = int(item["actual_end"])

        input_index = len(tts_inputs) // 2 + 1
        tts_inputs.extend(["-i", str(fitted_clip)])
        delay = actual_start
        label = f"d{input_index}"
        energy_gain_db = 0.0
        reference_energy_db: float | None = None
        dub_energy_db: float | None = None
        if DUB_ENABLE_ENERGY_MATCHING:
            reference_clip = reference_dir / f"{segment['id']}_orig.wav"
            try:
                if not reference_clip.exists() or reference_clip.stat().st_size <= 0:
                    extract_audio_clip(
                        source_video_path,
                        reference_clip,
                        max(int(segment["startMs"]), 0),
                        max(int(segment["endMs"]) - int(segment["startMs"]), 250),
                    )
                energy_gain_db, reference_energy_db, dub_energy_db = compute_energy_match_gain_db(
                    reference_clip,
                    fitted_clip,
                    max_gain_db=DUB_MAX_ENERGY_GAIN_DB,
                )
            except Exception:
                energy_gain_db = 0.0
        if abs(energy_gain_db) >= 0.15:
            filter_parts.append(f"[{input_index}:a]volume={energy_gain_db:.2f}dB,adelay={delay}|{delay}[{label}]")
        else:
            filter_parts.append(f"[{input_index}:a]adelay={delay}|{delay}[{label}]")
        mix_inputs.append(f"[{label}]")
        manifests.append(
            ClipManifest(
                index=index,
                segment_id=segment["id"],
                start_ms=actual_start,
                end_ms=actual_end,
                voice=voice,
                rate=rate,
                pitch=pitch,
                volume=volume,
                translated_text=translated,
                delivery=delivery,
                clip_ms=clip_ms,
                target_ms=target_ms,
                fitted_path=str(fitted_clip),
                reference_energy_db=reference_energy_db,
                dub_energy_db=dub_energy_db,
                energy_gain_db=round(energy_gain_db, 3),
            )
        )

    if not manifests:
        run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-t",
                f"{duration_seconds:.3f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-ac",
                str(STABLE_AUDIO_CHANNELS),
                "-ar",
                str(STABLE_AUDIO_SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(dub_audio_path),
            ]
        )
        return manifests

    filter_parts.append(
        "".join(mix_inputs)
        + f"amix=inputs={len(mix_inputs)}:normalize=0:duration=longest:dropout_transition=0[mix];"
        + f"[mix]{stable_audio_filter_chain()}[dub]"
    )
    emit_progress(
        phase="render",
        step="tts_mix",
        progress=0.61,
        message="Đang ghép toàn bộ clip lồng tiếng thành một track audio",
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-t",
            f"{duration_seconds:.3f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            *tts_inputs,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[dub]",
            "-ac",
            str(STABLE_AUDIO_CHANNELS),
            "-ar",
            str(STABLE_AUDIO_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(dub_audio_path),
        ]
    )
    return manifests


def normalize_audio_mix_mode(value: str | None, *, keep_original_audio: bool) -> str:
    normalized = normalize_text(value or "").lower().replace("-", "_")
    if normalized in {"preserve_background", "background_only", "music_only"}:
        return "preserve_background"
    if normalized in {"preserve_original_low", "original_low"}:
        return "preserve_original_low"
    if normalized in {"dub_only", "replace"}:
        return "dub_only"
    return "preserve_background" if keep_original_audio else "dub_only"


def extract_audio_for_background_mix(video_path: Path, audio_path: Path) -> None:
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
            "2",
            "-ar",
            "44100",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ],
        timeout=240.0,
    )


def torchaudio_source_separation_background(
    *,
    mix_path: Path,
    output_path: Path,
    phase: str,
    progress: float,
) -> Path:
    ensure_source_separation_runtime(phase=phase, step="background_prepare", progress=max(progress - 0.01, 0.0))
    emit_progress(
        phase=phase,
        step="background_prepare",
        progress=progress,
        message="Đang tách lời gốc khỏi nhạc nền bằng torchaudio HDemucs...",
    )
    import torch  # type: ignore
    import torchaudio  # type: ignore

    bundle_name = (DUB_SOURCE_SEPARATION_MODEL or "HDEMUCS_HIGH_MUSDB_PLUS").strip().upper()
    bundle = getattr(torchaudio.pipelines, bundle_name, None)
    if bundle is None:
        bundle = getattr(torchaudio.pipelines, "HDEMUCS_HIGH_MUSDB_PLUS")
    target_sample_rate = int(getattr(bundle, "sample_rate", 44100) or 44100)
    with temporarily_disable_dead_local_proxies(), temporarily_use_workspace_torch_home():
        model = bundle.get_model()

    # Determine device: try GPU first, fall back to CPU
    device = torch.device("cpu")
    if DUB_USE_GPU and torch.cuda.is_available():
        device = torch.device(f"cuda:{DUB_GPU_DEVICE}")
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass

    model = model.to(device)
    model.eval()
    waveform, sample_rate = torchaudio.load(str(mix_path))
    if waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)
    if waveform.size(0) == 1:
        waveform = waveform.repeat(2, 1)
    elif waveform.size(0) > 2:
        waveform = waveform[:2, :]
    if sample_rate != target_sample_rate:
        waveform = torchaudio.functional.resample(waveform, sample_rate, target_sample_rate)

    # --- Chunked processing to avoid GPU OOM on long audio ---
    chunk_seconds = 30
    chunk_samples = chunk_seconds * target_sample_rate
    total_samples = waveform.size(1)
    source_names = list(getattr(model, "sources", []) or ["drums", "bass", "other", "vocals"])
    non_vocal_indices = [idx for idx, name in enumerate(source_names) if str(name).lower() != "vocals"]
    if not non_vocal_indices:
        non_vocal_indices = list(range(len(source_names) - 1))

    num_chunks = max((total_samples + chunk_samples - 1) // chunk_samples, 1)
    safe_print(
        f"[info] HDemucs: processing {total_samples} samples in {num_chunks} chunks ({chunk_seconds}s each) on {device}",
        flush=True,
    )

    def _run_separation_on_device(dev):
        nonlocal model
        if next(model.parameters()).device != dev:
            model = model.to(dev)
        chunks = []
        for chunk_idx in range(num_chunks):
            start = chunk_idx * chunk_samples
            end = min(start + chunk_samples, total_samples)
            chunk_waveform = waveform[:, start:end].to(dev)
            with torch.inference_mode():
                separated = model(chunk_waveform.unsqueeze(0))
            if separated.dim() != 4 or separated.size(1) < 2:
                raise RuntimeError("HDemucs did not return the expected source stems.")
            bg_chunk = separated[0, non_vocal_indices, :, :].sum(dim=0).cpu()
            chunks.append(bg_chunk)
            del separated, chunk_waveform
            if dev.type == "cuda":
                torch.cuda.empty_cache()
        return chunks

    try:
        background_chunks = _run_separation_on_device(device)
    except RuntimeError as gpu_err:
        if device.type == "cuda" and ("out of memory" in str(gpu_err).lower() or "CUDA" in str(gpu_err)):
            safe_print(f"[warn] HDemucs GPU OOM, falling back to CPU: {gpu_err}", flush=True)
            torch.cuda.empty_cache()
            model = model.to(torch.device("cpu"))
            background_chunks = _run_separation_on_device(torch.device("cpu"))
        else:
            raise

    background = torch.cat(background_chunks, dim=1)
    background = background / max(background.abs().max().item(), 1.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(output_path), background.cpu(), target_sample_rate)

    # Final cleanup
    del model, background, background_chunks, waveform
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    validate_generated_audio_file(output_path, context="Background source separation")
    return output_path


def separate_background_audio(
    *,
    video_path: Path,
    output_dir: Path,
    phase: str,
    progress: float,
) -> Path:
    if not DUB_SOURCE_SEPARATION_ENABLED:
        raise RuntimeError("Source separation currently disabled.")
    output_dir.mkdir(parents=True, exist_ok=True)
    mix_path = output_dir / "source_full_mix.wav"
    extract_audio_for_background_mix(video_path, mix_path)
    if DUB_SOURCE_SEPARATION_PROVIDER.startswith("torchaudio"):
        return torchaudio_source_separation_background(
            mix_path=mix_path,
            output_path=output_dir / "background_no_vocals.wav",
            phase=phase,
            progress=progress,
        )
    ensure_source_separation_runtime(phase=phase, step="background_prepare", progress=max(progress - 0.01, 0.0))
    stem_name = mix_path.stem
    separation_root = output_dir / "separated"
    no_vocals_path = separation_root / DUB_SOURCE_SEPARATION_MODEL / stem_name / "no_vocals.wav"
    accompaniment_path = separation_root / DUB_SOURCE_SEPARATION_MODEL / stem_name / "accompaniment.wav"
    cached_candidate = no_vocals_path if no_vocals_path.exists() else accompaniment_path
    if cached_candidate.exists() and cached_candidate.stat().st_size > 0:
        return cached_candidate
    emit_progress(
        phase=phase,
        step="background_prepare",
        progress=progress,
        message="Đang tách lời gốc khỏi nhạc nền để giữ lại background audio...",
    )
    run(
        [
            sys.executable,
            "-m",
            "demucs.separate",
            "-n",
            DUB_SOURCE_SEPARATION_MODEL,
            "--two-stems",
            DUB_SOURCE_SEPARATION_STEM,
            "-o",
            str(separation_root),
            str(mix_path),
        ],
        timeout=float(DUB_SOURCE_SEPARATION_TIMEOUT),
    )
    candidate = no_vocals_path if no_vocals_path.exists() else accompaniment_path
    validate_generated_audio_file(candidate, context="Background source separation")
    return candidate


def prepare_background_audio_track(
    *,
    video_path: Path,
    video_meta: dict[str, Any],
    work_dir: Path,
    audio_mix_mode: str,
    keep_original_audio: bool,
    phase: str = "render",
    progress: float = 0.6,
) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    normalized_mode = normalize_audio_mix_mode(audio_mix_mode, keep_original_audio=keep_original_audio)
    if normalized_mode != "preserve_background":
        return None, warnings
    if not bool(video_meta.get("hasAudio")):
        warnings.append("Video gốc không có audio nền để giữ lại.")
        return None, warnings
    try:
        background_audio_path = separate_background_audio(
            video_path=video_path,
            output_dir=work_dir,
            phase=phase,
            progress=progress,
        )
        return background_audio_path, warnings
    except Exception as exc:
        warnings.append(
            "Không tách được lời gốc khỏi nhạc nền hoàn toàn, sẽ bỏ audio nền gốc và chỉ giữ voice mới"
            " cùng nhạc nền bổ sung (nếu có): "
            f"{normalize_text(str(exc))[:180]}"
        )
        return None, warnings


def create_final_audio(
    video_path: Path,
    dub_audio_path: Path,
    output_path: Path,
    *,
    audio_mix_mode: str,
    keep_original_audio: bool,
    background_audio_path: Path | None = None,
    background_music_path: Path | None = None,
    background_music_volume: float = 0.0,
) -> None:
    normalized_mode = normalize_audio_mix_mode(audio_mix_mode, keep_original_audio=keep_original_audio)
    target_duration_ms = max(
        ffprobe_duration_ms(video_path),
        ffprobe_audio_duration_ms(dub_audio_path),
    )
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-t",
        f"{target_duration_ms / 1000:.3f}",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
    ]
    filter_parts: list[str] = ["[0:a]anull[base]"]
    mix_inputs: list[str] = ["[base]"]
    input_index = 1
    input_index, background_music_label = append_looped_background_music_input(
        command,
        filter_parts,
        background_music_path=background_music_path,
        background_music_volume=background_music_volume,
        target_duration_ms=target_duration_ms,
        input_index=input_index,
        label="bgm",
    )
    if background_music_label:
        mix_inputs.append(background_music_label)
    if normalized_mode == "preserve_background" and background_audio_path and background_audio_path.exists():
        command.extend(["-i", str(background_audio_path)])
        filter_parts.append(
            f"[{input_index}:a]volume={max(min(DUB_BACKGROUND_AUDIO_GAIN, 1.5), 0.0):.3f}[bed]"
        )
        mix_inputs.append("[bed]")
        input_index += 1
    elif normalized_mode == "preserve_original_low" and keep_original_audio:
        has_video_audio = False
        try:
            has_video_audio = bool(get_video_meta(video_path).get("hasAudio"))
        except Exception:
            has_video_audio = False
        if has_video_audio:
            command.extend(["-i", str(video_path)])
            filter_parts.append(
                f"[{input_index}:a]volume={max(min(DUB_ORIGINAL_AUDIO_FALLBACK_GAIN, 0.5), 0.0):.3f}[orig]"
            )
            mix_inputs.append("[orig]")
            input_index += 1
    command.extend(["-i", str(dub_audio_path)])
    mix_inputs.append(f"[{input_index}:a]")
    if len(mix_inputs) == 1:
        filter_parts.append(f"{mix_inputs[0]}anull[mix]")
    else:
        filter_parts.append(
            "".join(mix_inputs)
            + f"amix=inputs={len(mix_inputs)}:normalize=0:duration=longest:dropout_transition=0[mix]"
        )
    filter_parts.append(
        f"[mix]atrim=0:{target_duration_ms / 1000:.3f},{stable_audio_filter_chain()}[aout]"
    )
    run(
        [
            *command,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[aout]",
            "-ac",
            str(STABLE_AUDIO_CHANNELS),
            "-ar",
            str(STABLE_AUDIO_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        timeout=240.0 if background_music_label else 180.0,
    )
