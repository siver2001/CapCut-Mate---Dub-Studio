from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from .common import *
from .analysis import (
    is_vieneu_voice_preset,
    resolve_edge_voice_name,
    resolve_tts_output_extension,
    resolve_vieneu_prompt_audio,
    resolve_voice_preset,
    should_use_vieneu_voice,
)
from .runtime import (
    ensure_edge_tts_runtime,
    ensure_source_separation_runtime,
    temporarily_disable_dead_local_proxies,
    temporarily_use_workspace_torch_home,
)

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
) -> None:
    if not has_audio or not use_background_audio:
        run(["ffmpeg", "-y", "-i", str(intro_voice_path), "-c:a", "pcm_s16le", str(output_path)], timeout=60.0)
        return
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_clip_path),
            "-i",
            str(intro_voice_path),
            "-filter_complex",
            f"[0:a]volume={max(min(background_volume, 0.3), 0.0):.3f}[bed];[bed][1:a]amix=inputs=2:normalize=0:duration=longest[aout]",
            "-map",
            "[aout]",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        timeout=120.0
    )


def estimate_spoken_text_profile(text: str) -> dict[str, float]:
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
        len(words) / 3.15 if words else 0.0,
        spoken_units / 13.6 if spoken_units else 0.0,
        0.78 if chars <= 16 else 1.02,
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
    if intro:
        pitch_hz += 3
        volume_percent += 2
    if "NamMinh" in voice:
        pitch_hz = max(pitch_hz - 1, -18)
    pitch_hz = max(min(pitch_hz, 14), -18)
    volume_percent = max(min(volume_percent, 6), -4)
    return {
        "spokenText": build_spoken_text(spoken, source, normalized_delivery),
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
            min_rate, max_rate = (-2, 40)
        else:
            min_rate, max_rate = (-6, 28) if timing_mode == "balanced_natural" else (-10, 34)
    else:
        if ultra_tight:
            min_rate, max_rate = (-6, 34)
        else:
            min_rate, max_rate = (-10, 22) if timing_mode == "balanced_natural" else (-14, 28)
    return max(min_rate, min(percent, max_rate))


def format_rate_percent(percent: int, timing_mode: str = "balanced_natural", *, intro: bool = False) -> str:
    return f"{clamp_rate_percent(percent, timing_mode=timing_mode, intro=intro):+d}%"


def estimate_rate(text: str, target_ms: int, timing_mode: str = "balanced_natural") -> str:
    target_ms = max(target_ms, 900)
    target_seconds = target_ms / 1000
    profile = estimate_spoken_text_profile(text)
    pressure = profile["expectedSeconds"] / max(target_seconds, 0.1)
    percent = int(round((pressure - 1.0) * (96 if is_ultra_tight_mode(timing_mode) else 84)))
    if target_seconds < 1.35:
        percent += 7 if is_ultra_tight_mode(timing_mode) else 4
    elif target_seconds > 3.1:
        percent -= 1 if is_ultra_tight_mode(timing_mode) else 2
    return format_rate_percent(percent, timing_mode=timing_mode)


def estimate_intro_rate(text: str, target_ms: int, timing_mode: str = "balanced_natural") -> str:
    target_ms = max(target_ms, 1600)
    target_seconds = target_ms / 1000
    profile = estimate_spoken_text_profile(text)
    pressure = max(profile["expectedSeconds"] * 0.88, 1.1) / max(target_seconds, 0.1)
    percent = int(round((pressure - 1.0) * (92 if is_ultra_tight_mode(timing_mode) else 82))) + (
        12 if is_ultra_tight_mode(timing_mode) else 8
    )
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
    max_delta = 10 if target_ms >= 1700 else 12
    if str(delivery or "").strip().lower() in {"excited", "urgent"}:
        max_delta += 3
    if abs(current_percent - previous_percent) <= 4:
        current_percent = int(round((current_percent * 2 + previous_percent) / 3))
    else:
        current_percent = previous_percent + max(min(current_percent - previous_percent, max_delta), -max_delta)
    return format_rate_percent(current_percent, timing_mode=timing_mode, intro=intro)


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
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
            boundary="SentenceBoundary" if use_boundary else None,
        )
        await asyncio.wait_for(communicate.save(str(output_path)), timeout=EDGE_TTS_TIMEOUT)


def _normalize_edge_tts_text(text: str, *, preserve_pauses: bool) -> str:
    clean = normalize_text(text).replace("\ufeff", "")
    clean = re.sub(r"[\u200b-\u200f\u2060]", "", clean)
    clean = (
        clean.replace("“", '"')
        .replace("â€", '"')
        .replace("’", "'")
        .replace("…", "...")
    )
    if not preserve_pauses:
        clean = normalize_tts_period_pauses(clean)
    return normalize_text(clean)


def sanitize_edge_tts_text(text: str) -> str:
    clean = _normalize_edge_tts_text(text, preserve_pauses=False)
    from ..subtitle_utils import collapse_repeated_words

    clean = collapse_repeated_words(clean)
    return normalize_text(clean)


def ensure_edge_tts_terminal_punctuation(text: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    clean = clean.rstrip(" ,;:")
    if not clean:
        return ""
    if clean.endswith(("...", "â€¦", "?", "!")):
        return clean.replace("â€¦", "...")
    if clean.endswith("."):
        return clean
    return f"{clean}."


def strip_trailing_vietnamese_filler(text: str) -> str:
    from ..subtitle_utils import VIETNAMESE_FILLER_SUFFIXES

    clean = normalize_text(text)
    if not clean:
        return ""
    punctuation = ""
    while clean and clean[-1] in ".!?…":
        punctuation = clean[-1] + punctuation
        clean = clean[:-1].rstrip()
    lowered = clean.lower()
    for suffix in sorted(VIETNAMESE_FILLER_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(f" {suffix}"):
            clean = clean[: -len(suffix)].rstrip(" ,;:-")
            break
    clean = clean.strip()
    if not clean:
        return ""
    return f"{clean}{punctuation}"


def build_edge_tts_safe_rewrites(text: str) -> list[str]:
    clean = normalize_text(text)
    if not clean:
        return []
    rewrites: list[str] = []
    patterns = (
        (r"^Tại sao lại (.+)\?$", lambda body: [f"Sao phải {body}?", f"Vì sao {body}?"]),
        (r"^Tại sao (.+)\?$", lambda body: [f"Vì sao {body}?", f"Sao {body}?"]),
        (r"^Vì sao lại (.+)\?$", lambda body: [f"Vì sao {body}?", f"Sao phải {body}?"]),
    )
    for pattern, builder in patterns:
        match = re.match(pattern, clean, flags=re.IGNORECASE)
        if not match:
            continue
        body = match.group(1).strip()
        for candidate in builder(body):
            normalized = normalize_text(candidate)
            if normalized and normalized not in rewrites:
                rewrites.append(normalized)
    return rewrites


def build_tts_text_candidates(spoken_text: str, translated_text: str = "") -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _push(value: str) -> None:
        normalized = ensure_edge_tts_terminal_punctuation(normalize_text(value))
        if normalized and normalized not in seen:
            seen.add(normalized)
            candidates.append(normalized)

    for raw_text in (spoken_text, translated_text):
        preserved = _normalize_edge_tts_text(raw_text, preserve_pauses=True)
        if not preserved:
            continue
        _push(preserved)
        trimmed_filler = strip_trailing_vietnamese_filler(preserved)
        if trimmed_filler and trimmed_filler != preserved:
            _push(trimmed_filler)
        for rewrite in build_edge_tts_safe_rewrites(trimmed_filler or preserved):
            _push(rewrite)
        sanitized = sanitize_edge_tts_text(raw_text)
        if sanitized and sanitized != preserved:
            _push(sanitized)
    return candidates


def edge_tts_output_looks_hallucinated(text: str, clip_ms: int) -> bool:
    clean = normalize_text(text)
    if not clean:
        return False
    profile = estimate_spoken_text_profile(clean)
    expected_ms = max(int(profile["expectedSeconds"] * 1000), 520)
    words = int(profile["words"])
    chars = int(profile["chars"])
    if words <= 3:
        return clip_ms > max(int(expected_ms * 2.15), expected_ms + 1400)
    if words <= 8 or chars <= 42:
        return clip_ms > max(int(expected_ms * 1.75), expected_ms + 1600)
    return clip_ms > max(int(expected_ms * 1.60), expected_ms + 2000)


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
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size <= 0:
        output_path.unlink(missing_ok=True)
    selected_voice = resolve_voice_preset(voice)
    prompt_audio = resolve_vieneu_prompt_audio(
        speaker_id=speaker_id,
        job_id=job_id,
    )
    if is_vieneu_voice_preset(selected_voice) and DUB_USE_VIENEU:
        try:
            from tools.vieneu_wrapper import get_vieneu_provider

            safe_print(
                f"Đang khởi động VieNeu-TTS cho {speaker_id} (lần đầu có thể mất 10-20 giây)...",
                flush=True,
            )
            provider = get_vieneu_provider()
            success = provider.synthesize(
                text,
                output_path,
                voice_name=selected_voice,
                prompt_audio=prompt_audio,
            )
            if success:
                validate_generated_audio_file(output_path, context="VieNeu-TTS synthesis")
                return
        except Exception as e:
            safe_print(f"VieNeu-TTS synthesis failed, falling back to edge-tts: {e}")
    elif is_vieneu_voice_preset(selected_voice):
        if not DUB_USE_VIENEU:
            safe_print("VieNeu-TTS dang tat trong cau hinh, fallback sang edge-tts.", flush=True)
        else:
            safe_print(
                f"Khong tim thay mau speaker hop le cho {speaker_id}, fallback sang edge-tts.",
                flush=True,
            )

    edge_voice = resolve_edge_voice_name(selected_voice)
    edge_text = ensure_edge_tts_terminal_punctuation(_normalize_edge_tts_text(text, preserve_pauses=True))
    sanitized_edge_text = ensure_edge_tts_terminal_punctuation(sanitize_edge_tts_text(text))
    stripped_filler_text = ensure_edge_tts_terminal_punctuation(strip_trailing_vietnamese_filler(edge_text))
    if not edge_text:
        raise RuntimeError("Edge TTS synthesis skipped because spoken text is empty after cleanup.")

    temp_output_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    temp_output_path.unlink(missing_ok=True)
    last_error = "unknown error"

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

        try:
            asyncio.run(
                _generate_tts_async(
                    current_text,
                    edge_voice,
                    rate if attempt < 3 else "+0%",
                    temp_output_path,
                    pitch=pitch if attempt < 3 else "+0Hz",
                    volume=volume if attempt < 3 else "+0%",
                    use_boundary=current_use_boundary,
                )
            )
            validate_generated_audio_file(temp_output_path, context="Edge TTS synthesis")
            clip_ms = ffprobe_audio_duration_ms(temp_output_path)
            if edge_tts_output_looks_hallucinated(current_text, clip_ms):
                raise RuntimeError(
                    f"Edge TTS output looks hallucinated ({clip_ms}ms for {len(current_text.split())} words)"
                )
            temp_output_path.replace(output_path)
            return
        except Exception as exc:
            last_error = str(exc)
            temp_output_path.unlink(missing_ok=True)
            if attempt < 3:
                safe_print(
                    f"Edge TTS retry {attempt + 2}/4 for voice {edge_voice}: {last_error} (Text length: {len(current_text)})"
                )
                time.sleep(0.6 * (attempt + 1))

    raise RuntimeError(f"Edge TTS synthesis failed for voice {edge_voice}: {last_error}")


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
    return fit_audio_length_with_mode(source_path, output_path, target_ms, timing_mode="balanced_natural")


def fit_audio_length_with_mode(source_path: Path, output_path: Path, target_ms: int, timing_mode: str) -> int:
    clip_ms = ffprobe_audio_duration_ms(source_path)
    ultra_tight = is_ultra_tight_mode(timing_mode)
    target_fill_ms = max(int(target_ms * (0.996 if ultra_tight else 0.985)), 700)
    if abs(clip_ms - target_fill_ms) <= (35 if ultra_tight else 80):
        run(["ffmpeg", "-y", "-i", str(source_path), str(output_path)], timeout=60.0)
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
    lead_guard = min(36 if ultra_tight else 60, gap_before // (4 if ultra_tight else 3))
    tail_allowance = min(int(gap_after * (0.18 if ultra_tight else 0.48)), 120 if ultra_tight else 260)
    target_ms = base_duration - lead_guard - (40 if ultra_tight else 70) + tail_allowance
    max_available = max(next_start - start_ms - (40 if ultra_tight else 70), 520)
    profile = estimate_spoken_text_profile(text or segment.get("spokenText") or segment.get("translatedText") or segment.get("sourceText") or "")
    punctuation_bonus = 80 if normalize_text(text or "").endswith(("?", "!", "...", "…")) else 0
    speech_floor = int(profile["expectedSeconds"] * 1000) + punctuation_bonus
    min_target = 600 if ultra_tight else 620 if base_duration < 1200 else 760
    target_ms = max(int(target_ms), min(speech_floor, int(max_available)))
    return max(min(int(target_ms), int(max_available)), min_target)


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
    adjustment = int(round((ratio - 1.0) * (96 if ultra_tight else 78)))
    if ratio > (1.22 if ultra_tight else 1.35):
        adjustment += 6 if ultra_tight else 4
    elif ratio < (0.84 if ultra_tight else 0.75):
        adjustment -= 6 if ultra_tight else 4
    next_percent = parse_rate_percent(current_rate) + adjustment
    return format_rate_percent(next_percent, timing_mode=timing_mode, intro=intro)


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
) -> tuple[Path, int, str, str, str, str]:
    delivery_profile = build_tts_delivery_profile(
        text=translated,
        source_text=source_text or translated,
        voice=voice,
        delivery="excited" if intro else delivery,
        intro=intro,
    )
    spoken_text = normalize_tts_period_pauses(delivery_profile["spokenText"])
    pitch = delivery_profile["pitch"]
    volume = delivery_profile["volume"]
    rate = estimate_intro_rate(spoken_text, target_ms, timing_mode=timing_mode) if intro else estimate_rate(spoken_text, target_ms, timing_mode=timing_mode)
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
    text_candidates = build_tts_text_candidates(spoken_text, translated)

    for _ in range(4 if ultra_tight else 3):
        if rate in seen_rates:
            break
        seen_rates.add(rate)
        rate_candidate: dict[str, Any] | None = None
        last_synthesis_error: Exception | None = None
        for candidate_text in text_candidates:
            cache_key = hashlib.sha1(f"{speaker_id}|{voice}|{rate}|{pitch}|{volume}|{candidate_text}".encode("utf-8")).hexdigest()[:16]
            raw_extension = resolve_tts_output_extension(
                voice=voice,
                speaker_id=speaker_id,
                job_id=job_id,
            )
            raw_stem = f"{index:04d}_{cache_key}"
            # VieNeu emits WAV directly. Keep a distinct raw path so FFmpeg never
            # tries to read and write the same file while fitting duration.
            if raw_extension == ".wav":
                raw_clip = tts_dir / f"{raw_stem}_raw{raw_extension}"
            else:
                raw_clip = tts_dir / f"{raw_stem}{raw_extension}"
            fit_key = hashlib.sha1(
                f"{cache_key}|{target_ms}|{timing_mode}".encode("utf-8")
            ).hexdigest()[:12]
            fitted_clip = tts_dir / f"{index:04d}_{cache_key}_{fit_key}.wav"
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
                    synthesize_tts(candidate_text, voice, rate, raw_clip, pitch=pitch, volume=volume, speaker_id=speaker_id, job_id=job_id)
                except Exception as exc:
                    last_synthesis_error = exc
                    if candidate_text != spoken_text:
                        safe_print(
                            f"Falling back to safer TTS text for segment {index}: {exc}",
                            flush=True,
                        )
                    continue
            raw_ms = ffprobe_audio_duration_ms(raw_clip)
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
                else fit_audio_length_with_mode(raw_clip, fitted_clip, target_ms, timing_mode)
            )
            fit_error = abs(clip_ms - target_ms)
            pressure_penalty = abs(math.log(max(raw_ms / max(target_ms, 1), 0.001))) * (220 if ultra_tight else 180)
            rate_candidate = {
                "path": fitted_clip,
                "clipMs": clip_ms,
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "spokenText": candidate_text,
                "score": fit_error + pressure_penalty,
                "fitError": fit_error,
                "rawMs": raw_ms,
            }
            break
        if rate_candidate is None:
            if last_synthesis_error is not None:
                raise last_synthesis_error
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
        raise RuntimeError("Could not synthesize a timed TTS clip.")
    return (
        Path(best["path"]),
        int(best["clipMs"]),
        str(best["rate"]),
        str(best["pitch"]),
        str(best["volume"]),
        str(best["spokenText"]),
    )


def _tts_provider_for_voice(voice: str) -> str:
    selected_voice = resolve_voice_preset(voice)
    if is_vieneu_voice_preset(selected_voice) and DUB_USE_VIENEU:
        return "vieneu"
    return "edge"


def _run_tts_chain(
    *,
    items: list[dict[str, Any]],
    total_segments: int,
    timing_mode: str,
    tts_dir: Path,
    job_id: str,
) -> list[dict[str, Any]]:
    chain_results: list[dict[str, Any]] = []
    previous_rate: str | None = None
    for item in items:
        emit_progress(
            phase="render",
            step="tts",
            progress=0.44 + (item["progress_index"] / max(total_segments, 1)) * 0.16,
            message=(
                f"Đang tạo lồng tiếng {item['progress_index']}/{total_segments}"
                f" · {item['speaker_id']} · {item['voice']}"
            ),
        )
        fitted_clip, clip_ms, rate, pitch, volume, spoken_text = synthesize_timed_tts_clip(
            index=item["index"],
            speaker_id=item["speaker_id"],
            voice=item["voice"],
            translated=item["spoken_text"],
            source_text=item["source_text"],
            delivery=item["delivery"],
            target_ms=item["target_ms"],
            timing_mode=timing_mode,
            tts_dir=tts_dir,
            previous_rate=previous_rate,
            job_id=job_id,
        )
        previous_rate = rate
        chain_results.append(
            {
                **item,
                "fitted_clip": fitted_clip,
                "clip_ms": clip_ms,
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "spoken_text": spoken_text,
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
            continue
        delivery = normalize_text(segment.get("delivery") or "neutral").lower() or "neutral"
        # spokenText is already processed by build_spoken_text during translation.
        # Do NOT call build_spoken_text again — it would double-inject fillers,
        # pauses, and delivery modifications, causing stuttered/repeated words.
        spoken_text = collapse_repeated_words(
            normalize_text(segment.get("spokenText") or translated)
        )
        if not spoken_text:
            continue
        speaker_id = segment.get("speakerId") or "speaker_1"
        voice = voices.get(speaker_id) or DEFAULT_VOICES[(index - 1) % len(DEFAULT_VOICES)]
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
            text=spoken_text,
        )
        fitted_clip, clip_ms, rate, pitch, volume, spoken_text = synthesize_timed_tts_clip(
            index=index,
            speaker_id=speaker_id,
            voice=voice,
            translated=spoken_text,
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
                spoken_text=spoken_text,
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
            continue
        delivery = normalize_text(segment.get("delivery") or "neutral").lower() or "neutral"
        spoken_text = collapse_repeated_words(normalize_text(segment.get("spokenText") or translated))
        if not spoken_text:
            continue
        speaker_id = segment.get("speakerId") or "speaker_1"
        voice = voices.get(speaker_id) or DEFAULT_VOICES[(index - 1) % len(DEFAULT_VOICES)]
        prepared_items.append(
            {
                "index": index,
                "segment": segment,
                "translated": translated,
                "spoken_text": spoken_text,
                "speaker_id": speaker_id,
                "voice": voice,
                "delivery": delivery,
                "target_ms": resolve_segment_target_ms(
                    segments,
                    index - 1,
                    video_duration_ms=int(video_meta.get("durationMs", 0)),
                    timing_mode=timing_mode,
                    text=spoken_text,
                ),
                "source_text": segment.get("sourceText") or translated,
                "provider": _tts_provider_for_voice(voice),
            }
        )

    total_segments = max(len(prepared_items), 1)
    for progress_index, item in enumerate(prepared_items, start=1):
        item["progress_index"] = progress_index

    generated_items: list[dict[str, Any]] = []
    if prepared_items:
        provider_limits = {
            "edge": EDGE_TTS_CONCURRENCY,
            "vieneu": VIENEU_TTS_CONCURRENCY,
        }
        for provider in ("edge", "vieneu"):
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
                        )
                        for chain in chains
                    ]
                    for future in as_completed(futures):
                        generated_items.extend(future.result())
            else:
                for chain in chains:
                    generated_items.extend(
                        _run_tts_chain(
                            items=chain,
                            total_segments=total_segments,
                            timing_mode=timing_mode,
                            tts_dir=tts_dir,
                            job_id=job_id,
                        )
                    )
    generated_items.sort(key=lambda item: int(item["index"]))

    for item in generated_items:
        index = int(item["index"])
        segment = item["segment"]
        translated = str(item["translated"])
        spoken_text = str(item["spoken_text"])
        voice = str(item["voice"])
        delivery = str(item["delivery"])
        target_ms = int(item["target_ms"])
        fitted_clip = Path(item["fitted_clip"])
        clip_ms = int(item["clip_ms"])
        rate = str(item["rate"])
        pitch = str(item["pitch"])
        volume = str(item["volume"])

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
                start_ms=int(segment["startMs"]),
                end_ms=int(segment["endMs"]),
                voice=voice,
                rate=rate,
                pitch=pitch,
                volume=volume,
                translated_text=translated,
                spoken_text=spoken_text,
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

    filter_parts.append(
        "".join(mix_inputs)
        + f"amix=inputs={len(mix_inputs)}:normalize=0:duration=longest:dropout_transition=0[dub]"
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
            "Không tách được lời gốc khỏi nhạc nền hoàn toàn, sẽ fallback sang trộn audio gốc mức rất thấp: "
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
) -> None:
    normalized_mode = normalize_audio_mix_mode(audio_mix_mode, keep_original_audio=keep_original_audio)
    if normalized_mode == "preserve_background" and background_audio_path and background_audio_path.exists():
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(background_audio_path),
                "-i",
                str(dub_audio_path),
                "-filter_complex",
                f"[0:a]volume={max(min(DUB_BACKGROUND_AUDIO_GAIN, 1.5), 0.0):.3f}[bed];[bed][1:a]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0[aout]",
                "-map",
                "[aout]",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            timeout=180.0,
        )
        return
    if normalized_mode in {"preserve_background", "preserve_original_low"} and keep_original_audio:
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-i",
                str(dub_audio_path),
                "-filter_complex",
                f"[0:a]volume={max(min(DUB_ORIGINAL_AUDIO_FALLBACK_GAIN, 0.5), 0.0):.3f}[orig];[orig][1:a]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0[aout]",
                "-map",
                "[aout]",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ]
        )
        return
    if not keep_original_audio:
        run(["ffmpeg", "-y", "-i", str(dub_audio_path), "-c:a", "pcm_s16le", str(output_path)], timeout=120.0)
        return
    run(["ffmpeg", "-y", "-i", str(dub_audio_path), "-c:a", "pcm_s16le", str(output_path)], timeout=120.0)
