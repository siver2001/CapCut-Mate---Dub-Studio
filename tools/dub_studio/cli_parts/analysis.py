from __future__ import annotations

from .common import *
from .runtime import (
    ensure_whisperx_align_cache,
    get_transcription_model_path,
    hf_repo_cached,
    import_whisperx_module,
    parse_json_response_payload,
    preferred_whisperx_compute_type,
    preferred_whisperx_device,
    resolve_hf_token,
    run_llama_cpp_prompt,
    run_ollama_prompt,
    should_use_ollama,
    should_use_llama_cpp,
    whisperx_align_repo_id,
    whisperx_asr_repo_id,
    whisperx_audio_waveform,
)

def subtitles_from_analysis_segments(segments: list[dict[str, Any]]) -> list[SubtitleLine]:
    subtitles: list[SubtitleLine] = []
    for index, item in enumerate(segments, start=1):
        text = normalize_text(item.get("text") or item.get("sourceText") or "")
        if not text:
            continue
        start_ms = max(int(item.get("startMs", 0)), 0)
        end_ms = max(int(item.get("endMs", start_ms + 1)), start_ms + 1)
        subtitles.append(
            SubtitleLine(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                content=text,
            )
        )
    return subtitles


def merge_whisperx_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in segments:
        text = normalize_text(raw.get("text") or raw.get("sourceText") or "")
        if not text:
            continue
        item = {
            "startMs": max(int(raw.get("startMs", 0)), 0),
            "endMs": max(int(raw.get("endMs", 0)), max(int(raw.get("startMs", 0)), 0) + 1),
            "text": text,
            "speaker": normalize_text(raw.get("speaker") or raw.get("speakerId") or ""),
        }
        if current is None:
            current = item
            continue
        gap = item["startMs"] - current["endMs"]
        merged_span = item["endMs"] - current["startMs"]
        combined = f"{current['text']} {item['text']}".strip()
        same_speaker = item["speaker"] == current["speaker"]
        if same_speaker and gap <= 550 and merged_span <= 6500 and len(combined) <= 110:
            current = {
                **current,
                "endMs": item["endMs"],
                "text": combined,
            }
            continue
        merged.append(current)
        current = item
    if current is not None:
        merged.append(current)
    return merged


def remap_speaker_segments(
    segments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str]:
    labeled = [item for item in segments if normalize_text(item.get("speaker") or "")]
    if not labeled:
        return [], {}, "speaker_1"
    usage_count: dict[str, int] = {}
    total_duration_ms: dict[str, int] = {}
    total_chars: dict[str, int] = {}
    turn_count: dict[str, int] = {}
    previous_speaker = ""
    for item in labeled:
        raw_speaker = normalize_text(item.get("speaker") or "")
        usage_count[raw_speaker] = usage_count.get(raw_speaker, 0) + 1
        total_duration_ms[raw_speaker] = total_duration_ms.get(raw_speaker, 0) + max(
            int(item.get("endMs", 0)) - int(item.get("startMs", 0)),
            0,
        )
        total_chars[raw_speaker] = total_chars.get(raw_speaker, 0) + len(
            normalize_text(item.get("text") or "").replace(" ", "")
        )
        if previous_speaker and previous_speaker != raw_speaker:
            turn_count[raw_speaker] = turn_count.get(raw_speaker, 0) + 1
        turn_count.setdefault(raw_speaker, turn_count.get(raw_speaker, 0))
        previous_speaker = raw_speaker
    ranked_speakers = sorted(
        usage_count,
        key=lambda speaker_id: (
            total_duration_ms.get(speaker_id, 0) + turn_count.get(speaker_id, 0) * 220 + usage_count.get(speaker_id, 0) * 140,
            total_chars.get(speaker_id, 0),
        ),
        reverse=True,
    )
    remap = {
        raw_speaker: f"speaker_{index + 1}"
        for index, raw_speaker in enumerate(ranked_speakers)
    }
    remapped_segments: list[dict[str, Any]] = []
    for item in labeled:
        speaker_id = remap[normalize_text(item.get("speaker") or "")]
        remapped_segments.append(
            {
                **item,
                "speakerId": speaker_id,
            }
        )
    speaker_stats = {
        remap[raw_speaker]: {
            "speakerId": remap[raw_speaker],
            "segmentCount": usage_count.get(raw_speaker, 0),
            "totalDurationMs": total_duration_ms.get(raw_speaker, 0),
            "totalChars": total_chars.get(raw_speaker, 0),
            "turnCount": turn_count.get(raw_speaker, 0),
        }
        for raw_speaker in ranked_speakers
    }
    return remapped_segments, speaker_stats, "speaker_1"


def extract_speaker_samples(video_path: Path, segments: list[dict[str, Any]], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    speaker_samples: dict[str, list[dict[str, Any]]] = {}
    for seg in segments:
        sid = seg.get("speakerId") or seg.get("speaker")
        if not sid:
            continue
        speaker_samples.setdefault(sid, []).append(seg)
    
    result: dict[str, Path] = {}
    for sid, segs in speaker_samples.items():
        def segment_score(item: dict[str, Any]) -> tuple[float, float, float]:
            duration_ms = max(int(item["endMs"]) - int(item["startMs"]), 1)
            text = normalize_text(item.get("text") or item.get("sourceText") or "")
            chars = len(text.replace(" ", ""))
            duration_penalty = abs(duration_ms - 5500)
            short_penalty = 2400 if duration_ms < 1600 else 0
            text_penalty = 180 if chars < 18 else 0
            return (duration_penalty + short_penalty + text_penalty, -chars, int(item["startMs"]))

        best_seg = sorted(segs, key=segment_score)[0]
        best_duration_ms = min(max(int(best_seg["endMs"]) - int(best_seg["startMs"]), 1800), 9000)
        sample_path = output_dir / f"{sid}_sample.wav"
        try:
            extract_audio_clip(video_path, sample_path, int(best_seg["startMs"]), best_duration_ms)
            result[sid] = sample_path
        except Exception:
            pass
    return result


def estimate_gender_from_sample_audio(sample_path: Path | str | None) -> dict[str, Any]:
    """Gender estimation disabled — always returns unknown."""
    return {"gender": "unknown", "confidence": 0.0, "medianPitchHz": None}


def _estimate_gender_from_audio_array(audio: Any, sr: int = 16000) -> dict[str, Any]:
    """Gender estimation disabled — always returns unknown."""
    return {"gender": "unknown", "confidence": 0.0, "medianPitchHz": None}


def estimate_gender_from_audio_slice(
    audio: Any,
    *,
    sr: int,
    start_ms: int,
    end_ms: int,
) -> dict[str, Any]:
    """Gender estimation disabled — always returns unknown."""
    return {"gender": "unknown", "confidence": 0.0, "medianPitchHz": None}


def build_speaker_stats_from_segments(
    segments: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str]:
    speaker_stats: dict[str, dict[str, Any]] = {}
    previous_speaker = ""
    for item in segments:
        speaker_id = normalize_text(item.get("speakerId") or "")
        if not speaker_id:
            continue
        stats = speaker_stats.setdefault(
            speaker_id,
            {
                "speakerId": speaker_id,
                "segmentCount": 0,
                "totalDurationMs": 0,
                "totalChars": 0,
                "turnCount": 0,
            },
        )
        stats["segmentCount"] += 1
        stats["totalDurationMs"] += max(int(item.get("endMs", 0)) - int(item.get("startMs", 0)), 0)
        stats["totalChars"] += len(normalize_text(item.get("text") or item.get("sourceText") or "").replace(" ", ""))
        if previous_speaker and previous_speaker != speaker_id:
            stats["turnCount"] += 1
        previous_speaker = speaker_id
    if not speaker_stats:
        return {}, "speaker_1"
    ranked = sorted(
        speaker_stats.values(),
        key=lambda item: (
            item["totalDurationMs"] + item["turnCount"] * 220 + item["segmentCount"] * 140,
            item["totalChars"],
        ),
        reverse=True,
    )
    return speaker_stats, ranked[0]["speakerId"]


def collapse_segments_to_gender_buckets(
    segments: list[dict[str, Any]],
    *,
    audio: Any,
    sr: int = 16000,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str, int, float, str]:
    """Simplified: gender-based speaker bucketing is disabled.

    All segments are assigned to their existing speakerId (or speaker_1
    as fallback).  The function signature is preserved so callers do not
    need to change.
    """
    if not segments:
        return segments, {}, "speaker_1", 1, 0.42, "single_voice"

    remapped_segments = [
        {**segment, "speakerId": segment.get("speakerId") or "speaker_1"}
        for segment in segments
    ]
    speaker_stats, main_speaker_id = build_speaker_stats_from_segments(remapped_segments)
    speaker_count = max(len(speaker_stats), 1)
    voice_layout = "single_voice"
    return remapped_segments, speaker_stats, main_speaker_id, speaker_count, 0.42, voice_layout


def analyze_with_whisperx(
    *,
    video_path: Path,
    audio_path: Path,
    raw_srt_path: Path,
    merged_srt_path: Path,
    language: str | None = None,
) -> dict[str, Any]:
    whisperx = import_whisperx_module()
    extract_audio_for_whisperx(video_path, audio_path)
    device = preferred_whisperx_device()
    compute_type = preferred_whisperx_compute_type(device)
    audio = whisperx.load_audio(str(audio_path))
    waveform = whisperx_audio_waveform(audio)
    warnings: list[str] = []
    if DUB_USE_GPU and device != "cuda":
        warnings.append("WhisperX đang chạy CPU vì torch trong môi trường hiện tại chưa bật CUDA.")
    whisperx_repo_id = WHISPERX_ASR_REPO or whisperx_asr_repo_id(WHISPERX_MODEL)
    if whisperx_repo_id and not hf_repo_cached(whisperx_repo_id):
        raise RuntimeError(
            f"WhisperX model {WHISPERX_MODEL} chua co local cache. Hay chay prepare de tai model ve may."
        )
    model = whisperx.load_model(
        WHISPERX_MODEL,
        device,
        compute_type=compute_type,
        language=language,
        asr_options={"condition_on_previous_text": False},
        download_root=str(HUGGINGFACE_HUB_CACHE),
        local_files_only=bool(whisperx_repo_id),
        threads=WHISPERX_THREADS,
    )
    result = model.transcribe(audio, batch_size=WHISPERX_BATCH_SIZE, language=language)
    detected_language = normalize_text(result.get("language") or "") or "zh"
    raw_segments = result.get("segments") or []

    emit_progress(phase="analysis", step="align", progress=0.35, message=f"Đang tải mô hình căn chỉnh (align) cho ngôn ngữ: {detected_language}...")
    align_repo_id = whisperx_align_repo_id(detected_language)
    align_kwargs: dict[str, Any] = {}
    if align_repo_id:
        if not hf_repo_cached(align_repo_id):
            ensure_whisperx_align_cache(
                language_code=detected_language,
                phase="analysis",
                step="align",
                progress=0.35,
            )
        align_kwargs = {
            "model_name": align_repo_id,
            "model_dir": str(HUGGINGFACE_HUB_CACHE),
            "model_cache_only": True,
        }
    model_align, metadata = whisperx.load_align_model(
        language_code=detected_language,
        device=device,
        **align_kwargs,
    )
    emit_progress(phase="analysis", step="align", progress=0.45, message="Đang căn chỉnh thời gian từ vựng (word-level alignment)...")
    aligned_result = whisperx.align(
        raw_segments,
        model_align,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )
    aligned_segments = aligned_result.get("segments") or []
    diarization_used = False
    hf_token = resolve_hf_token()
    diarization_repo_id = normalize_text(WHISPERX_DIARIZATION_MODEL)
    if hf_token or hf_repo_cached(diarization_repo_id):
        try:
            if not diarization_repo_id or not hf_repo_cached(diarization_repo_id):
                raise RuntimeError("model diarization local chua san sang")
            emit_progress(phase="analysis", step="diarize", progress=0.55, message="Đang tải mô hình nhận diện người nói (PyAnnote Diarization)...")
            diarize_model = whisperx.DiarizationPipeline(
                model_name=diarization_repo_id,
                token=hf_token,
                device=device,
                cache_dir=str(HUGGINGFACE_HUB_CACHE),
            )
            emit_progress(phase="analysis", step="diarize", progress=0.65, message="Đang phân tích và phân biệt giọng người nói...")
            diarize_segments = diarize_model(
                waveform,
                min_speakers=1,
                max_speakers=WHISPERX_DIARIZATION_MAX_SPEAKERS,
            )
            aligned_result = whisperx.assign_word_speakers(diarize_segments, aligned_result)
            aligned_segments = aligned_result.get("segments") or []
            diarization_used = True
        except Exception as exc:
            warnings.append(f"WhisperX diarization không chạy được, sẽ fallback heuristic speaker: {exc}")
    else:
        warnings.append("Chưa có HF token cho WhisperX diarization, sẽ fallback heuristic speaker.")

    normalized_segments = [
        {
            "startMs": max(int(float(segment.get("start", 0.0)) * 1000), 0),
            "endMs": max(int(float(segment.get("end", 0.0)) * 1000), max(int(float(segment.get("start", 0.0)) * 1000), 0) + 1),
            "text": normalize_text(segment.get("text") or ""),
            "speaker": normalize_text(segment.get("speaker") or ""),
        }
        for segment in aligned_segments
        if normalize_text(segment.get("text") or "")
    ]
    raw_subtitles = subtitles_from_analysis_segments(normalized_segments)
    raw_srt_path.write_text(compose_srt(raw_subtitles), encoding="utf-8")

    if diarization_used:
        merged_segments = merge_whisperx_segments(normalized_segments)
        merged_srt_path.write_text(
            compose_srt(subtitles_from_analysis_segments(merged_segments)),
            encoding="utf-8",
        )
        remapped_segments, _, _ = remap_speaker_segments(merged_segments)
        if remapped_segments:
            (
                remapped_segments,
                speaker_stats,
                main_speaker_id,
                speaker_count,
                speaker_confidence,
                voice_layout,
            ) = collapse_segments_to_gender_buckets(
                remapped_segments,
                audio=audio,
                sr=16000,
            )
            return {
                "sourceLanguage": detected_language,
                "rawSubtitles": raw_subtitles,
                "mergedSegments": remapped_segments,
                "speakerStats": speaker_stats,
                "mainSpeakerId": main_speaker_id,
                "speakerCount": speaker_count,
                "speakerConfidence": speaker_confidence,
                "voiceLayout": voice_layout,
                "warnings": warnings,
            }
        warnings.append("WhisperX diarization không gán được speaker ổn định, sẽ fallback heuristic speaker.")

    merged_subtitles = merge_short_subtitles(raw_subtitles)
    merged_srt_path.write_text(compose_srt(merged_subtitles), encoding="utf-8")
    speaker_count, speaker_confidence = estimate_speaker_count(merged_subtitles)
    assignments, speaker_stats, main_speaker_id = assign_speakers(merged_subtitles, speaker_count)
    merged_segments = [
        {
            "startMs": subtitle.start_ms,
            "endMs": subtitle.end_ms,
            "text": subtitle.content,
            "speakerId": speaker_id,
        }
        for subtitle, speaker_id in zip(merged_subtitles, assignments)
    ]
    (
        merged_segments,
        speaker_stats,
        main_speaker_id,
        speaker_count,
        speaker_confidence,
        voice_layout,
    ) = collapse_segments_to_gender_buckets(
        merged_segments,
        audio=audio,
        sr=16000,
    )
    return {
        "sourceLanguage": detected_language,
        "rawSubtitles": raw_subtitles,
        "mergedSegments": merged_segments,
        "speakerStats": speaker_stats,
        "mainSpeakerId": main_speaker_id,
        "speakerCount": speaker_count,
        "speakerConfidence": speaker_confidence,
        "voiceLayout": voice_layout,
        "warnings": warnings,
    }

def transcribe_to_srt(video_path: Path, output_srt: Path, language: str | None = None, max_len: int = 32) -> None:
    if output_srt.exists() and output_srt.stat().st_size > 0:
        return
    model_path = get_transcription_model_path()
    relative_model = model_path.relative_to(ROOT).as_posix()
    relative_srt = output_srt.relative_to(ROOT).as_posix()
    options = [
        f"model={relative_model}",
        f"use_gpu={'true' if DUB_USE_GPU else 'false'}",
        f"gpu_device={DUB_GPU_DEVICE}",
        "format=srt",
        f"destination={relative_srt}",
        f"max_len={max_len}",
    ]
    if language:
        options.insert(1, f"language={language}")
    whisper_filter = f"whisper={':'.join(options)}"
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-af",
            whisper_filter,
            "-f",
            "null",
            "-",
        ],
        cwd=ROOT,
    )


def analyze_with_local_whisper(
    *,
    video_path: Path,
    raw_srt_path: Path,
    merged_srt_path: Path,
    language: str | None = None,
    fallback_reason: str = "",
    explicit_local_mode: bool = False,
) -> dict[str, Any]:
    transcribe_to_srt(video_path, raw_srt_path, language=language)
    raw_subtitles = parse_srt(raw_srt_path.read_text(encoding="utf-8-sig"))
    if not raw_subtitles:
        raise RuntimeError("Local ffmpeg-whisper did not return any subtitle segments.")

    merged_subtitles = merge_short_subtitles(raw_subtitles)
    merged_srt_path.write_text(compose_srt(merged_subtitles), encoding="utf-8")
    transcript_text = " ".join(item.content for item in raw_subtitles[:24])
    detected_language, _, _ = detect_source_language(transcript_text)
    speaker_count, speaker_confidence = estimate_speaker_count(merged_subtitles)
    assignments, speaker_stats, main_speaker_id = assign_speakers(merged_subtitles, speaker_count)
    merged_segments = [
        {
            "startMs": subtitle.start_ms,
            "endMs": subtitle.end_ms,
            "text": subtitle.content,
            "speakerId": speaker_id,
        }
        for subtitle, speaker_id in zip(merged_subtitles, assignments)
    ]
    try:
        import librosa

        local_audio_path = merged_srt_path.with_name(f"{merged_srt_path.stem}_audio.wav")
        extract_audio_for_whisperx(video_path, local_audio_path)
        local_audio, local_sr = librosa.load(str(local_audio_path), sr=16000, mono=True)
        (
            merged_segments,
            speaker_stats,
            main_speaker_id,
            speaker_count,
            speaker_confidence,
            voice_layout,
        ) = collapse_segments_to_gender_buckets(
            merged_segments,
            audio=local_audio,
            sr=local_sr,
        )
    except Exception:
        voice_layout = classify_voice_layout(merged_subtitles, speaker_count, speaker_confidence)
    if explicit_local_mode:
        warnings = [
            "WhisperX/Hugging Face da duoc tat boi cau hinh. He thong dang dung ffmpeg-whisper offline voi model local.",
            "Speaker diarization dang dung heuristic vi che do offline khong co gan speaker theo word.",
        ]
    else:
        warnings = [
            "WhisperX khong kha dung nen da fallback sang ffmpeg-whisper offline voi model local.",
            "Speaker diarization dang dung heuristic vi che do offline khong co gan speaker theo word.",
        ]
    if fallback_reason:
        warnings.append(
            f"{'Ly do dung che do local' if explicit_local_mode else 'Ly do fallback WhisperX'}: {fallback_reason}"
        )
    return {
        "sourceLanguage": detected_language,
        "rawSubtitles": raw_subtitles,
        "mergedSegments": merged_segments,
        "speakerStats": speaker_stats,
        "mainSpeakerId": main_speaker_id,
        "speakerCount": speaker_count,
        "speakerConfidence": speaker_confidence,
        "voiceLayout": voice_layout,
        "warnings": warnings,
    }


def detect_source_language(text: str) -> tuple[str, float, list[dict[str, Any]]]:
    if not text:
        alternatives = [{"code": code, "score": 0.0} for code in LANGUAGE_OPTIONS]
        return "zh", 0.15, alternatives
    hangul = sum(1 for ch in text if "\uac00" <= ch <= "\ud7a3")
    hiragana = sum(1 for ch in text if "\u3040" <= ch <= "\u309f")
    katakana = sum(1 for ch in text if "\u30a0" <= ch <= "\u30ff")
    kana = hiragana + katakana
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    meaningful = max(hangul + kana + cjk + latin, 1)
    scores = {
        "ko": hangul / meaningful,
        "ja": (kana * 1.35 + max(cjk - 20, 0) * 0.15) / meaningful,
        "zh": (cjk * 1.1) / meaningful,
        "en": latin / meaningful,
    }
    if scores["ja"] > 0:
        scores["zh"] *= 0.78
    if scores["ko"] > 0:
        scores["en"] *= 0.92
    best_code = max(scores, key=scores.get)
    confidence = max(0.18, min(scores[best_code] + 0.18, 0.97))
    alternatives = [{"code": code, "score": round(scores[code], 4)} for code in sorted(scores, key=scores.get, reverse=True)]
    return best_code, round(confidence, 4), alternatives


def ends_like_dialogue(text: str) -> bool:
    stripped = text.strip()
    return stripped.endswith(("?", "？", "!", "！", "...", "…", "。"))


def is_same_speaker_continuation(previous: SubtitleLine, current: SubtitleLine) -> bool:
    gap = max(current.start_ms - previous.end_ms, 0)
    previous_len = len(normalize_text(previous.content))
    current_len = len(normalize_text(current.content))
    if gap >= 1700:
        return True
    if gap <= 220 and not ends_like_dialogue(previous.content):
        return True
    if gap <= 360 and previous_len >= 30 and current_len >= 24:
        return True
    if gap <= 180 and abs(previous_len - current_len) >= 26:
        return True
    return False


def is_turn_exchange(previous: SubtitleLine, current: SubtitleLine) -> bool:
    gap = max(current.start_ms - previous.end_ms, 0)
    previous_len = len(normalize_text(previous.content))
    current_len = len(normalize_text(current.content))
    if gap > 1200:
        return False
    if ends_like_dialogue(previous.content) and gap <= 900:
        return True
    if gap <= 700 and previous_len <= 34 and current_len <= 34:
        return True
    if gap <= 460 and current_len <= 18:
        return True
    return False


def estimate_speaker_count(subtitles: list[SubtitleLine]) -> tuple[int, float]:
    if len(subtitles) < 3:
        return 1, 0.42

    turn_signals = 0.0
    rapid_exchanges = 0
    punctuation_exchanges = 0
    short_dialogue_exchanges = 0
    continuation_signals = 0
    for previous, current in zip(subtitles, subtitles[1:]):
        gap = current.start_ms - previous.end_ms
        if is_same_speaker_continuation(previous, current):
            continuation_signals += 1
            continue
        if is_turn_exchange(previous, current):
            turn_signals += 1.0
            if gap <= 420:
                rapid_exchanges += 1
            previous_len = len(normalize_text(previous.content))
            current_len = len(normalize_text(current.content))
            if ends_like_dialogue(previous.content):
                punctuation_exchanges += 1
            if gap <= 850 and previous_len <= 42 and current_len <= 42:
                short_dialogue_exchanges += 1

    score = (
        turn_signals
        + rapid_exchanges * 0.55
        + punctuation_exchanges * 0.35
        + short_dialogue_exchanges * 0.25
        - continuation_signals * 0.14
    )
    density = score / max(len(subtitles) - 1, 1)
    exchange_ratio = turn_signals / max(len(subtitles) - 1, 1)

    if (
        turn_signals >= 3
        and (rapid_exchanges >= 1 or punctuation_exchanges >= 2 or short_dialogue_exchanges >= 3)
        and exchange_ratio >= 0.18
    ):
        confidence = min(
            0.84,
            0.58
            + exchange_ratio * 0.45
            + rapid_exchanges * 0.03
            + punctuation_exchanges * 0.02,
        )
        if density < 0.48 or len(subtitles) < 10:
            return 2, round(confidence, 4)
        if density < 0.78 or len(subtitles) < 16:
            return 3, round(min(confidence - 0.04, 0.8), 4)
        return 4, round(min(confidence - 0.08, 0.76), 4)

    if density < 0.12 or score < 1.1:
        return 1, round(max(0.4, 0.72 - density * 0.55), 4)
    if density < 0.34 or len(subtitles) < 7:
        return 2, round(min(0.82, 0.52 + density * 0.52), 4)
    if density < 0.72 or len(subtitles) < 12:
        return 3, round(min(0.78, 0.48 + density * 0.36), 4)
    return 4, round(min(0.74, 0.46 + density * 0.3), 4)


def classify_voice_layout(
    subtitles: list[SubtitleLine],
    speaker_count: int,
    speaker_confidence: float,
) -> str:
    if speaker_count <= 1:
        return "single_voice"
    if speaker_confidence < 0.44:
        return "single_voice"

    exchange_signals = 0
    continuation_signals = 0
    rapid_exchanges = 0
    for previous, current in zip(subtitles, subtitles[1:]):
        if is_same_speaker_continuation(previous, current):
            continuation_signals += 1
        elif is_turn_exchange(previous, current):
            exchange_signals += 1
            if max(current.start_ms - previous.end_ms, 0) <= 500:
                rapid_exchanges += 1

    if exchange_signals >= 3 and (
        rapid_exchanges >= 1 or exchange_signals > continuation_signals
    ):
        return "multi_character"
    if exchange_signals <= max(1, continuation_signals // 2):
        return "single_voice"
    return "multi_character"


def assign_speakers(subtitles: list[SubtitleLine], speaker_count: int) -> tuple[list[str], dict[str, dict[str, Any]], str]:
    if speaker_count <= 1:
        stats = {
            "speaker_1": {
                "speakerId": "speaker_1",
                "segmentCount": len(subtitles),
                "totalDurationMs": sum(max(item.end_ms - item.start_ms, 0) for item in subtitles),
                "totalChars": sum(len(normalize_text(item.content).replace(" ", "")) for item in subtitles),
                "turnCount": max(len(subtitles) - 1, 0),
            }
        }
        return ["speaker_1"] * len(subtitles), stats, "speaker_1"

    speaker_ids = [f"speaker_{index + 1}" for index in range(speaker_count)]
    assignments: list[str] = []
    usage_count = {speaker_id: 0 for speaker_id in speaker_ids}
    total_duration_ms = {speaker_id: 0 for speaker_id in speaker_ids}
    total_chars = {speaker_id: 0 for speaker_id in speaker_ids}
    last_used_index = {speaker_id: -99 for speaker_id in speaker_ids}
    turn_count = {speaker_id: 0 for speaker_id in speaker_ids}

    def register_assignment(speaker_id: str, subtitle: SubtitleLine, subtitle_index: int) -> None:
        usage_count[speaker_id] += 1
        total_duration_ms[speaker_id] += max(subtitle.end_ms - subtitle.start_ms, 0)
        total_chars[speaker_id] += len(normalize_text(subtitle.content).replace(" ", ""))
        if assignments and assignments[-1] != speaker_id:
            turn_count[speaker_id] += 1
        last_used_index[speaker_id] = subtitle_index

    for idx, subtitle in enumerate(subtitles):
        if idx == 0:
            speaker_id = speaker_ids[0]
        else:
            previous = subtitles[idx - 1]
            previous_speaker = assignments[-1]
            available = [speaker_id for speaker_id in speaker_ids if usage_count[speaker_id] > 0]
            if is_same_speaker_continuation(previous, subtitle):
                speaker_id = previous_speaker
            elif is_turn_exchange(previous, subtitle):
                candidates = [speaker_id for speaker_id in available if speaker_id != previous_speaker]
                if not candidates and len(available) < speaker_count:
                    speaker_id = speaker_ids[len(available)]
                elif candidates:
                    speaker_id = sorted(
                        candidates,
                        key=lambda candidate: (
                            1 if idx - last_used_index[candidate] < 2 else 0,
                            -usage_count[candidate],
                            last_used_index[candidate],
                        ),
                    )[0]
                else:
                    speaker_id = previous_speaker
            else:
                gap = max(subtitle.start_ms - previous.end_ms, 0)
                if gap >= 2200 and len(available) < speaker_count:
                    speaker_id = speaker_ids[len(available)]
                else:
                    speaker_id = previous_speaker

        assignments.append(speaker_id)
        register_assignment(speaker_id, subtitle, idx)

    speaker_stats = {
        speaker_id: {
            "speakerId": speaker_id,
            "segmentCount": usage_count[speaker_id],
            "totalDurationMs": total_duration_ms[speaker_id],
            "totalChars": total_chars[speaker_id],
            "turnCount": turn_count[speaker_id],
        }
        for speaker_id in speaker_ids
        if usage_count[speaker_id] > 0
    }
    if not speaker_stats:
        return ["speaker_1"] * len(subtitles), {"speaker_1": {"speakerId": "speaker_1", "segmentCount": len(subtitles), "totalDurationMs": 0, "totalChars": 0, "turnCount": 0}}, "speaker_1"

    ranked_speakers = sorted(
        speaker_stats.values(),
        key=lambda item: (
            item["totalDurationMs"] + item["turnCount"] * 220 + item["segmentCount"] * 140,
            item["totalChars"],
        ),
        reverse=True,
    )
    remap = {
        item["speakerId"]: f"speaker_{index + 1}"
        for index, item in enumerate(ranked_speakers)
    }
    remapped_assignments = [remap.get(speaker_id, "speaker_1") for speaker_id in assignments]
    remapped_stats = {}
    for item in ranked_speakers:
        new_id = remap[item["speakerId"]]
        remapped_stats[new_id] = {
            **item,
            "speakerId": new_id,
        }
    return remapped_assignments, remapped_stats, "speaker_1"


def is_vieneu_voice_preset(candidate: str) -> bool:
    value = str(candidate or "").strip()
    return value == VIENEU_CLONE_PRESET or value in VIENEU_PRESET_VOICE_IDS


def is_valtec_reference_voice(candidate: str) -> bool:
    value = str(candidate or "").strip()
    return value in VALTEC_REFERENCE_VOICES


def is_valtec_voice_preset(candidate: str) -> bool:
    value = str(candidate or "").strip()
    return (
        value == VALTEC_CLONE_PRESET
        or value in VALTEC_PRESET_SPEAKER_IDS
        or value in VALTEC_REFERENCE_VOICES
    )


def resolve_vieneu_prompt_audio(*, speaker_id: str = "speaker_1", job_id: str = "") -> Path | None:
    if not job_id:
        return None
    sample_path = (
        DUB_STUDIO_DIR / job_id / "analysis" / "speakers" / f"{speaker_id or 'speaker_1'}_sample.wav"
    )
    if sample_path.exists():
        return sample_path
    return None


def resolve_valtec_prompt_audio(*, speaker_id: str = "speaker_1", job_id: str = "") -> Path | None:
    return resolve_vieneu_prompt_audio(speaker_id=speaker_id, job_id=job_id)


def resolve_valtec_reference_audio(voice: str) -> Path | None:
    selected_voice = resolve_voice_preset(voice)
    meta = VALTEC_REFERENCE_VOICES.get(selected_voice)
    if not meta:
        return None
    reference_path = VALTEC_REFERENCE_DIR / str(meta.get("filename") or "")
    return reference_path if reference_path.exists() else None


def should_use_vieneu_voice(*, voice: str, speaker_id: str = "speaker_1", job_id: str = "") -> bool:
    selected_voice = resolve_voice_preset(voice)
    if not DUB_USE_VIENEU or not is_vieneu_voice_preset(selected_voice):
        return False
    if selected_voice != VIENEU_CLONE_PRESET:
        return True
    return resolve_vieneu_prompt_audio(speaker_id=speaker_id, job_id=job_id) is not None


def should_use_valtec_voice(*, voice: str, speaker_id: str = "speaker_1", job_id: str = "") -> bool:
    selected_voice = resolve_voice_preset(voice)
    if not DUB_USE_VALTEC or not is_valtec_voice_preset(selected_voice):
        return False
    if selected_voice in VALTEC_REFERENCE_VOICES:
        return True
    if selected_voice != VALTEC_CLONE_PRESET:
        return True
    return resolve_valtec_prompt_audio(speaker_id=speaker_id, job_id=job_id) is not None


def resolve_tts_output_extension(*, voice: str, speaker_id: str = "speaker_1", job_id: str = "") -> str:
    return (
        ".wav"
        if should_use_vieneu_voice(voice=voice, speaker_id=speaker_id, job_id=job_id)
        or should_use_valtec_voice(voice=voice, speaker_id=speaker_id, job_id=job_id)
        else ".mp3"
    )


def resolve_edge_voice_name(candidate: str) -> str:
    value = str(candidate or "").strip()
    if value in EDGE_VOICE_PRESETS:
        return EDGE_VOICE_PRESETS[value]
    if value in EDGE_VOICE_PRESETS.values():
        return value
    if is_custom_edge_voice_name(value):
        return value
    return EDGE_VOICE_PRESETS["edge:male"]


def is_custom_edge_voice_name(candidate: str) -> bool:
    value = str(candidate or "").strip()
    if (
        not value
        or value in EDGE_VOICE_PRESETS
        or is_vieneu_voice_preset(value)
        or is_valtec_voice_preset(value)
    ):
        return False
    return bool(EDGE_VOICE_NAME_PATTERN.match(value))


def recommend_voice_preset(
    *,
    candidate: str,
    index: int = 0,
    estimated_gender: str = "unknown",
) -> str:
    value = str(candidate or "").strip()
    if value in VOICE_LABELS:
        return value
    if is_custom_edge_voice_name(value):
        return value
    if value in EDGE_VOICE_PRESETS.values():
        for preset_id, edge_voice in EDGE_VOICE_PRESETS.items():
            if edge_voice == value:
                return preset_id
    if value in VALTEC_REFERENCE_VOICES:
        return value
    normalized = normalize_text(value).lower().replace("-", "_")
    gender = normalize_text(estimated_gender).lower()
    female_reference_voices = (
        "valtec:nf",
        "valtec:sf",
    )
    male_reference_voices = (
        "valtec:nm1",
        "valtec:sm",
        "valtec:nm2",
    )
    if any(token in gender for token in ("female", "woman", "girl", "nu")):
        return female_reference_voices[index % len(female_reference_voices)]
    if any(token in gender for token in ("male", "man", "boy", "nam")):
        return male_reference_voices[index % len(male_reference_voices)]
    if any(token in normalized for token in ("female", "woman", "girl", "nu")):
        return female_reference_voices[index % len(female_reference_voices)]
    if any(token in normalized for token in ("male", "man", "boy", "nam")):
        return male_reference_voices[index % len(male_reference_voices)]
    return DEFAULT_VOICES[index % len(DEFAULT_VOICES)]


def resolve_voice_preset(candidate: str, *, index: int = 0) -> str:
    return recommend_voice_preset(candidate=candidate, index=index)


def build_speakers(
    count: int,
    voice_mapping: dict[str, str] | None = None,
    speaker_stats: dict[str, dict[str, Any]] | None = None,
    main_speaker_id: str = "speaker_1",
    refinement: dict[str, dict[str, Any]] | None = None,
    sample_paths: dict[str, Path | str] | None = None,
) -> list[dict[str, Any]]:
    voice_mapping = voice_mapping or {}
    speaker_stats = speaker_stats or {}
    refinement = refinement or {}
    sample_paths = sample_paths or {}
    speakers = []
    for index in range(count):
        speaker_id = f"speaker_{index + 1}"
        ref = refinement.get(speaker_id, {})
        sample_path = sample_paths.get(speaker_id)
        voice = resolve_voice_preset(
            recommend_voice_preset(
                candidate=voice_mapping.get(speaker_id) or ref.get("suggestedVoice") or "",
                index=index,
            ),
            index=index,
        )
        stats = speaker_stats.get(speaker_id, {})
        
        display_name = ref.get("displayName")
        if not display_name:
            display_name = "Nhân vật chính" if speaker_id == main_speaker_id else f"Nhân vật {index + 1}"

        speakers.append(
            {
                "speakerId": speaker_id,
                "displayName": display_name,
                "estimatedGender": "unknown",
                "sampleGenderConfidence": 0.0,
                "samplePitchHz": None,
                "voicePreset": voice,
                "voiceLabel": VOICE_LABELS.get(voice, voice),
                "colorTag": SPEAKER_COLORS[index % len(SPEAKER_COLORS)],
                "isPrimary": speaker_id == main_speaker_id,
                "segmentCount": int(stats.get("segmentCount", 0)),
                "totalDurationMs": int(stats.get("totalDurationMs", 0)),
                "samplePath": str(sample_path or ""),
                "voiceCloneReady": bool(sample_path),
            }
        )
    return speakers


def refine_speakers_with_ollama(
    segments: list[dict[str, Any]],
    speaker_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Use Gemma 4 to identify speaker roles and genders from context."""
    if not segments or not speaker_ids:
        return {}
        
    context_samples = []
    for sid in speaker_ids:
        # Get a few lines for this speaker
        lines = [s["sourceText"] for s in segments if s.get("speakerId") == sid][:5]
        if lines:
            context_samples.append(f"{sid}: {' | '.join(lines)}")
            
    if not context_samples:
        return {}

    prompt = (
        "You are a script analyst for video dubbing.\n"
        "Identify the role and gender for each speaker ID based on their dialogue context.\n"
        "Return ONLY a valid JSON object where keys are speaker IDs and values are objects with:\n"
        '- "displayName": a short descriptive name in Vietnamese (e.g., "Người dẫn chuyện", "Khách hàng nam").\n'
        '- "gender": "male", "female", or "unknown".\n'
        '- "suggestedVoice": a generic voice type (e.g., "female_young", "male_deep").\n'
        "Dialogue Samples:\n"
        f"{chr(10).join(context_samples)}"
    )
    
    try:
        response = run_ollama_prompt(prompt, temperature=0.2)
        refinement = parse_json_response_payload(response)
        if isinstance(refinement, dict):
            return refinement
    except Exception:
        pass
    if should_use_llama_cpp("auto"):
        try:
            response = run_llama_cpp_prompt(
                prompt,
                max_tokens=max(256, len(speaker_ids) * 96),
                temperature=max(0.15, min(LLAMA_CPP_TEMP, 0.35)),
            )
            refinement = parse_json_response_payload(response)
            if isinstance(refinement, dict):
                return refinement
        except Exception:
            pass
    return {}


def _usable_local_llm_backends(provider: str) -> tuple[bool, bool]:
    """Return usable (ollama, llama.cpp) backends for optional speaker tasks."""
    ollama_ready = False
    llama_cpp_ready = False
    try:
        ollama_ready = should_use_ollama(provider)
    except Exception:
        ollama_ready = False
    try:
        llama_cpp_ready = should_use_llama_cpp(provider)
    except Exception:
        llama_cpp_ready = False
    return ollama_ready, llama_cpp_ready


def _run_optional_local_llm_json_prompt(
    prompt: str,
    *,
    provider: str,
    max_tokens: int,
    temperature: float = 0.1,
) -> Any | None:
    ollama_ready, llama_cpp_ready = _usable_local_llm_backends(provider)
    if ollama_ready:
        try:
            response = run_ollama_prompt(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return parse_json_response_payload(response)
        except Exception:
            pass
    if llama_cpp_ready:
        try:
            response = run_llama_cpp_prompt(
                prompt,
                max_tokens=max_tokens,
                temperature=max(0.08, min(temperature, 0.25)),
            )
            return parse_json_response_payload(response)
        except Exception:
            pass
    return None


def speaker_subtitles_from_segments(segments: list[dict[str, Any]]) -> list[SubtitleLine]:
    subtitles: list[SubtitleLine] = []
    for index, item in enumerate(segments, start=1):
        text = normalize_text(item.get("sourceText") or item.get("text") or "")
        if not text:
            continue
        subtitles.append(
            SubtitleLine(
                index=int(item.get("index") or index),
                start_ms=max(int(item.get("startMs", 0)), 0),
                end_ms=max(int(item.get("endMs", 0)), max(int(item.get("startMs", 0)), 0) + 1),
                content=text,
            )
        )
    return subtitles


def infer_speaker_assignments_with_llm(
    segments: list[dict[str, Any]],
    *,
    provider: str,
    max_speakers: int = 4,
) -> tuple[list[str], int, float] | None:
    if len(segments) < 4 or len(segments) > 72:
        return None

    transcript_lines: list[str] = []
    for index, item in enumerate(segments, start=1):
        text = normalize_text(item.get("sourceText") or item.get("text") or "")
        if not text:
            continue
        start_ms = max(int(item.get("startMs", 0)), 0)
        end_ms = max(int(item.get("endMs", start_ms + 1)), start_ms + 1)
        transcript_lines.append(
            f"[{index}] {start_ms/1000:.2f}-{end_ms/1000:.2f}s | {text[:180]}"
        )
    if len(transcript_lines) != len(segments):
        return None

    prompt = (
        "You are assigning recurring speakers for a dubbing transcript.\n"
        "Decide whether the transcript is narration/monologue or a dialogue with 2-4 recurring speakers.\n"
        "Return JSON only with this schema:\n"
        '{'
        '"speakerCount": 1, '
        '"confidence": 0.0, '
        '"assignments": [{"index": 1, "speakerId": "speaker_1"}]'
        '}\n'
        "Rules:\n"
        f"- speakerCount must be between 1 and {max_speakers}.\n"
        "- assignments must include every transcript index exactly once.\n"
        "- speakerId values must be speaker_1, speaker_2, speaker_3, or speaker_4.\n"
        "- Reuse the same speakerId consistently across the whole transcript.\n"
        "- Prefer fewer speakers unless the dialogue clearly alternates between people.\n"
        "- If the transcript looks like one narrator, use only speaker_1.\n"
        "Transcript:\n"
        f"{chr(10).join(transcript_lines)}"
    )
    payload = _run_optional_local_llm_json_prompt(
        prompt,
        provider=provider,
        max_tokens=max(320, len(segments) * 24),
        temperature=0.08,
    )
    if not isinstance(payload, dict):
        return None

    raw_assignments = payload.get("assignments")
    if not isinstance(raw_assignments, list) or len(raw_assignments) != len(segments):
        return None

    allowed_ids = {f"speaker_{index + 1}" for index in range(max_speakers)}
    assignment_map: dict[int, str] = {}
    for item in raw_assignments:
        if not isinstance(item, dict):
            return None
        try:
            index = int(item.get("index"))
        except Exception:
            return None
        speaker_id = normalize_text(item.get("speakerId") or "")
        if index < 1 or index > len(segments) or speaker_id not in allowed_ids:
            return None
        assignment_map[index] = speaker_id
    if len(assignment_map) != len(segments):
        return None

    assignments = [assignment_map[index] for index in range(1, len(segments) + 1)]
    used_ids = list(dict.fromkeys(assignments))
    if not used_ids:
        return None
    remap = {
        speaker_id: f"speaker_{index + 1}"
        for index, speaker_id in enumerate(used_ids)
    }
    normalized_assignments = [remap[item] for item in assignments]
    inferred_count = max(1, min(len(set(normalized_assignments)), max_speakers))
    raw_confidence = payload.get("confidence", 0.68)
    try:
        confidence = float(raw_confidence)
    except Exception:
        confidence = 0.68
    return normalized_assignments, inferred_count, max(0.45, min(confidence, 0.9))


def estimate_speaker_count_with_llm(
    segments: list[dict[str, Any]],
    *,
    provider: str,
    max_speakers: int = 4,
) -> tuple[int, float] | None:
    if len(segments) < 4:
        return None

    sampled_segments = segments
    if len(sampled_segments) > 40:
        step = (len(sampled_segments) - 1) / 39.0
        indexes = sorted({int(round(step * offset)) for offset in range(40)})
        sampled_segments = [sampled_segments[index] for index in indexes]

    transcript_lines = []
    for index, item in enumerate(sampled_segments, start=1):
        text = normalize_text(item.get("sourceText") or item.get("text") or "")
        if not text:
            continue
        start_ms = max(int(item.get("startMs", 0)), 0)
        end_ms = max(int(item.get("endMs", start_ms + 1)), start_ms + 1)
        transcript_lines.append(
            f"[{index}] {start_ms/1000:.2f}-{end_ms/1000:.2f}s | {text[:180]}"
        )
    if len(transcript_lines) < 4:
        return None

    prompt = (
        "You are estimating how many recurring speakers appear in a dubbing transcript.\n"
        "Count only recurring human speakers, not scene changes.\n"
        "Return JSON only with this schema:\n"
        '{"speakerCount": 1, "confidence": 0.0}\n'
        f"speakerCount must be between 1 and {max_speakers}.\n"
        "Prefer fewer speakers unless the transcript clearly alternates between people.\n"
        "Transcript sample:\n"
        f"{chr(10).join(transcript_lines)}"
    )
    payload = _run_optional_local_llm_json_prompt(
        prompt,
        provider=provider,
        max_tokens=128,
        temperature=0.08,
    )
    if not isinstance(payload, dict):
        return None
    try:
        speaker_count = max(1, min(int(payload.get("speakerCount", 1)), max_speakers))
    except Exception:
        return None
    try:
        confidence = float(payload.get("confidence", 0.66))
    except Exception:
        confidence = 0.66
    return speaker_count, max(0.45, min(confidence, 0.88))


def maybe_upgrade_speaker_segmentation_with_llm(
    segments: list[dict[str, Any]],
    *,
    speaker_count: int,
    speaker_confidence: float,
    voice_layout: str,
    provider: str,
) -> tuple[list[dict[str, Any]], int, float, str, dict[str, dict[str, Any]], str, str]:
    if not segments:
        return segments, speaker_count, speaker_confidence, voice_layout, {}, "speaker_1", ""

    should_try = (
        speaker_count <= 1
        or voice_layout == "single_voice"
        or speaker_confidence < 0.56
    )
    if not should_try:
        return segments, speaker_count, speaker_confidence, voice_layout, {}, "speaker_1", ""

    subtitles = speaker_subtitles_from_segments(segments)
    if len(subtitles) < 4:
        return segments, speaker_count, speaker_confidence, voice_layout, {}, "speaker_1", ""

    llm_assignments = infer_speaker_assignments_with_llm(
        segments,
        provider=provider,
    )
    note = ""
    if llm_assignments is not None:
        assignments, inferred_count, inferred_confidence = llm_assignments
        updated_segments = [
            {
                **segment,
                "speakerId": assignments[index],
            }
            for index, segment in enumerate(segments)
        ]
        assigned_like_segments = [
            {
                "startMs": item["startMs"],
                "endMs": item["endMs"],
                "text": item.get("sourceText") or "",
                "speaker": item.get("speakerId") or "speaker_1",
            }
            for item in updated_segments
        ]
        remapped_segments, remapped_stats, main_speaker_id = remap_speaker_segments(
            assigned_like_segments
        )
        if len(remapped_stats) > 1:
            normalized_segments = []
            for segment, mapped in zip(updated_segments, remapped_segments):
                normalized_segments.append(
                    {
                        **segment,
                        "speakerId": mapped.get("speakerId") or segment.get("speakerId") or "speaker_1",
                    }
                )
            boosted_confidence = max(speaker_confidence, inferred_confidence)
            boosted_layout = classify_voice_layout(
                subtitles,
                max(len(remapped_stats), inferred_count),
                boosted_confidence,
            )
            note = (
                f"Gemma 4 suy luận transcript có {len(remapped_stats)} speaker thay vì {speaker_count}. "
                "Nên kiểm tra lại mapping giọng nếu video có nhiều cảnh chuyển nhanh."
            )
            return (
                normalized_segments,
                max(len(remapped_stats), 1),
                boosted_confidence,
                boosted_layout,
                remapped_stats,
                main_speaker_id,
                note,
            )

    llm_count = estimate_speaker_count_with_llm(
        segments,
        provider=provider,
    )
    if llm_count is None:
        return segments, speaker_count, speaker_confidence, voice_layout, {}, "speaker_1", ""

    inferred_count, inferred_confidence = llm_count
    if inferred_count <= max(speaker_count, 1):
        return segments, speaker_count, speaker_confidence, voice_layout, {}, "speaker_1", ""

    assignments, inferred_stats, main_speaker_id = assign_speakers(subtitles, inferred_count)
    if len(inferred_stats) <= 1:
        return segments, speaker_count, speaker_confidence, voice_layout, {}, "speaker_1", ""

    updated_segments = [
        {
            **segment,
            "speakerId": assignments[index],
        }
        for index, segment in enumerate(segments)
    ]
    boosted_confidence = max(speaker_confidence, inferred_confidence)
    boosted_layout = classify_voice_layout(subtitles, inferred_count, boosted_confidence)
    note = (
        f"Gemma 4 suy luận transcript có khoảng {inferred_count} speaker và đã ép tách vai thoại. "
        "Nên kiểm tra lại mapping giọng nếu clip có độc thoại hoặc voice-over."
    )
    return (
        updated_segments,
        inferred_count,
        boosted_confidence,
        boosted_layout,
        inferred_stats,
        main_speaker_id,
        note,
    )


def smooth_signal(values: list[float], radius: int = 2) -> list[float]:
    if radius <= 0 or len(values) <= 2:
        return values[:]
    smoothed: list[float] = []
    for index in range(len(values)):
        start = max(index - radius, 0)
        end = min(index + radius + 1, len(values))
        window = values[start:end]
        smoothed.append(sum(window) / max(len(window), 1))
    return smoothed


def collect_active_ranges(scores: list[float], threshold: float, min_len: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for index, score in enumerate(scores):
        if score >= threshold:
            if start is None:
                start = index
            continue
        if start is not None and index - start >= min_len:
            ranges.append((start, index))
        start = None
    if start is not None and len(scores) - start >= min_len:
        ranges.append((start, len(scores)))
    return ranges


SOURCE_SUBTITLE_DETECTION_CONFIDENCE = 0.16


def snap_axis(value: int, step: int) -> int:
    return int(round(value / max(step, 1))) * max(step, 1)


def region_bounds(region: dict[str, Any]) -> tuple[int, int, int, int]:
    x = int(region.get("x", 0))
    y = int(region.get("y", 0))
    return x, y, x + int(region.get("w", 0)), y + int(region.get("h", 0))


def union_regions(region_a: dict[str, Any], region_b: dict[str, Any], *, video_meta: dict[str, Any]) -> dict[str, Any]:
    ax1, ay1, ax2, ay2 = region_bounds(region_a)
    bx1, by1, bx2, by2 = region_bounds(region_b)
    x1 = max(min(ax1, bx1), 0)
    y1 = max(min(ay1, by1), 0)
    x2 = min(max(ax2, bx2), int(video_meta["width"]))
    y2 = min(max(ay2, by2), int(video_meta["height"]))
    merged = {
        **region_a,
        **region_b,
        "x": x1,
        "y": y1,
        "w": max(x2 - x1, 1),
        "h": max(y2 - y1, 1),
    }
    merged["centerX"] = merged["x"] + merged["w"] // 2
    merged["centerY"] = merged["y"] + merged["h"] // 2
    return quantize_region(merged, video_meta=video_meta)


def expand_subtitle_region(region: dict[str, Any], *, video_meta: dict[str, Any]) -> dict[str, Any]:
    confidence = float(region.get("confidence", 0.0))
    width = int(region.get("w", 0))
    height = int(region.get("h", 0))
    pad_x = max(28, int(width * 0.18), int(video_meta["width"] * 0.025))
    pad_y = max(14, int(height * 0.34), int(video_meta["height"] * 0.012))
    if confidence < 0.38:
        pad_x += max(18, int(width * 0.10))
        pad_y += max(8, int(height * 0.14))
    x = max(int(region.get("x", 0)) - pad_x, 0)
    y = max(int(region.get("y", 0)) - pad_y, 0)
    right = min(int(region.get("x", 0)) + width + pad_x, int(video_meta["width"]))
    bottom = min(int(region.get("y", 0)) + height + pad_y, int(video_meta["height"]))
    expanded_w = max(right - x, 1)
    expanded_h = max(bottom - y, 1)
    # Keep enough room for anti-aliased caption edges and longer source captions.
    max_expanded_w = max(width * 4, int(video_meta["width"] * 0.86))
    if expanded_w > max_expanded_w:
        center_x = x + expanded_w // 2
        expanded_w = max_expanded_w
        x = max(center_x - expanded_w // 2, 0)
        right = min(x + expanded_w, int(video_meta["width"]))
        expanded_w = max(right - x, 1)
    expanded = {**region, "x": x, "y": y, "w": expanded_w, "h": expanded_h}
    expanded["centerX"] = expanded["x"] + expanded["w"] // 2
    expanded["centerY"] = expanded["y"] + expanded["h"] // 2
    return quantize_region(expanded, video_meta=video_meta)


def subtitle_region_detected(region: dict[str, Any] | None) -> bool:
    if not region:
        return False
    if not bool(region.get("detected")):
        return False
    return float(region.get("confidence", 0.0)) >= SOURCE_SUBTITLE_DETECTION_CONFIDENCE


def detect_subtitle_region_in_frame(
    frame: bytes,
    *,
    sample_width: int,
    sample_height: int,
    video_meta: dict[str, Any],
    fallback_region: dict[str, Any],
) -> dict[str, Any]:
    if len(frame) < sample_width * sample_height:
        return fallback_region

    margin_x = max(int(sample_width * 0.06), 8)
    row_scores = [0.0] * sample_height
    for y in range(1, sample_height - 1):
        row_start = y * sample_width
        previous = frame[row_start + margin_x]
        edge_score = 0.0
        contrast_score = 0.0
        ink_score = 0.0
        for x in range(margin_x + 1, sample_width - margin_x):
            value = frame[row_start + x]
            diff = abs(value - previous)
            if diff > 14:
                edge_score += 0.7
            if diff > 28:
                contrast_score += 1.15
            if value >= 206 or value <= 52:
                ink_score += 0.4
            elif value >= 178 or value <= 84:
                ink_score += 0.16
            previous = value
        score = edge_score + contrast_score + ink_score
        if y >= int(sample_height * 0.52):
            score *= 1.03
        row_scores[y] = score

    row_scores = smooth_signal(row_scores, radius=max(int(sample_height * 0.01), 2))
    average_row_score = sum(row_scores) / max(len(row_scores), 1)
    peak_row_score = max(row_scores) if row_scores else 0.0
    candidate_ranges = collect_active_ranges(
        row_scores,
        threshold=max(average_row_score * 1.28, peak_row_score * 0.46, 8.0),
        min_len=max(int(sample_height * 0.025), 9),
    )

    if not candidate_ranges:
        peak_index = row_scores.index(peak_row_score) if row_scores else max(sample_height // 2, 0)
        band_height = max(int(sample_height * 0.10), 18)
        peak_start = max(peak_index - band_height // 2, 0)
        candidate_ranges = [(peak_start, min(peak_start + band_height, sample_height))]

    fallback_center_y = int(
        ((int(fallback_region.get("y", 0)) + int(fallback_region.get("h", 0)) // 2) / max(int(video_meta["height"]), 1))
        * sample_height
    )
    fallback_width_ratio = min(max(int(fallback_region.get("w", 0)) / max(int(video_meta["width"]), 1), 0.22), 0.92)
    scale_x = video_meta["width"] / sample_width
    scale_y = video_meta["height"] / sample_height
    best_candidate: dict[str, Any] | None = None
    best_candidate_score = -1.0

    for raw_start, raw_end in candidate_ranges:
        start = max(raw_start - 4, 0)
        end = min(raw_end + 4, sample_height)
        band_height = max(end - start, 1)
        band_score = sum(row_scores[start:end])
        center_y = (start + end) // 2
        center_penalty = abs(center_y - fallback_center_y) / max(sample_height, 1)
        vertical_bias = 1.0 - min(center_penalty * 0.28, 0.16)
        if band_height > int(sample_height * 0.20):
            vertical_bias *= 0.84
        elif band_height < int(sample_height * 0.035):
            vertical_bias *= 0.88

        col_scores = [0.0] * sample_width
        for x in range(margin_x, sample_width - margin_x):
            previous = frame[start * sample_width + x]
            score = 0.0
            for y in range(start + 1, end):
                value = frame[y * sample_width + x]
                diff = abs(value - previous)
                if diff > 16:
                    score += 0.65
                if diff > 30:
                    score += 1.05
                if value >= 206 or value <= 50:
                    score += 0.22
                elif value >= 178 or value <= 84:
                    score += 0.08
                previous = value
            col_scores[x] = score

        col_scores = smooth_signal(col_scores, radius=max(int(sample_width * 0.008), 2))
        usable_scores = col_scores[margin_x : max(sample_width - margin_x, margin_x + 1)]
        average_col_score = sum(usable_scores) / max(len(usable_scores), 1)
        peak_col_score = max(usable_scores) if usable_scores else 0.0
        min_span = max(int(sample_width * 0.09), 20)
        spans = collect_active_ranges(
            col_scores,
            threshold=max(average_col_score * 1.22, peak_col_score * 0.43, 2.2),
            min_len=min_span,
        )
        spans = [(max(span_start, margin_x), min(span_end, sample_width - margin_x)) for span_start, span_end in spans]
        spans = [span for span in spans if span[1] - span[0] >= min_span]

        if not spans:
            fallback_left = int((int(fallback_region.get("x", 0)) / max(int(video_meta["width"]), 1)) * sample_width)
            fallback_width = int((int(fallback_region.get("w", sample_width)) / max(int(video_meta["width"]), 1)) * sample_width)
            left = max(fallback_left, 0)
            right = min(left + max(fallback_width, int(sample_width * 0.48)), sample_width - 1)
            chosen_span_score = band_score * 0.55
        else:
            chosen_span: tuple[int, int] | None = None
            chosen_span_score = -1.0
            for span_start, span_end in spans:
                span_width = max(span_end - span_start, 1)
                width_ratio = span_width / max(sample_width, 1)
                width_bias = 1.0
                if width_ratio < 0.16:
                    width_bias *= 0.76
                elif width_ratio > 0.90:
                    width_bias *= 0.82
                elif 0.24 <= width_ratio <= 0.82:
                    width_bias *= 1.06
                if abs(width_ratio - fallback_width_ratio) <= 0.14:
                    width_bias *= 1.04
                span_score = sum(col_scores[span_start:span_end]) * width_bias
                if span_score > chosen_span_score:
                    chosen_span_score = span_score
                    chosen_span = (span_start, span_end)
            left = chosen_span[0] if chosen_span else margin_x
            right = (chosen_span[1] - 1) if chosen_span else sample_width - margin_x - 1

        region_x = int(max((left - 10) * scale_x, 0))
        region_y = int(max((start - 4) * scale_y, 0))
        region_w = int(max(((right - left) + 10) * scale_x, video_meta["width"] * 0.18))
        region_h = int(max(((end - start) + 4) * scale_y, video_meta["height"] * 0.045))
        region_w = min(region_w, video_meta["width"] - region_x)
        region_h = min(region_h, video_meta["height"] - region_y)
        region_center_y = region_y + region_h // 2
        fallback_center_y_full = int(fallback_region.get("y", 0)) + int(fallback_region.get("h", 0)) // 2
        fallback_distance = abs(region_center_y - fallback_center_y_full) / max(int(video_meta["height"]), 1)
        confidence = (band_score / max(sample_width * band_height * 0.16, 1.0)) * vertical_bias
        confidence += min(chosen_span_score / max(sample_height * max(right - left, 1) * 0.18, 1.0), 1.35) * 0.22
        confidence *= 1.0 - min(fallback_distance * 0.18, 0.12)
        candidate = {
            "detected": True,
            "cleanupMode": fallback_region.get("cleanupMode", "localized_blur"),
            "x": max(region_x, 0),
            "y": max(region_y, 0),
            "w": max(region_w, 1),
            "h": max(region_h, 1),
            "centerX": max(region_x + region_w // 2, 0),
            "centerY": max(region_y + region_h // 2, 0),
            "confidence": round(confidence, 4),
        }
        candidate_score = confidence * (1.0 if candidate["w"] <= int(video_meta["width"] * 0.92) else 0.88)
        if candidate_score > best_candidate_score:
            best_candidate = candidate
            best_candidate_score = candidate_score

    if not best_candidate:
        return fallback_region

    return {
        **best_candidate,
        "detected": float(best_candidate.get("confidence", 0.0)) >= SOURCE_SUBTITLE_DETECTION_CONFIDENCE,
    }


def region_iou(region_a: dict[str, Any], region_b: dict[str, Any]) -> float:
    ax1 = int(region_a.get("x", 0))
    ay1 = int(region_a.get("y", 0))
    ax2 = ax1 + int(region_a.get("w", 0))
    ay2 = ay1 + int(region_a.get("h", 0))
    bx1 = int(region_b.get("x", 0))
    by1 = int(region_b.get("y", 0))
    bx2 = bx1 + int(region_b.get("w", 0))
    by2 = by1 + int(region_b.get("h", 0))
    inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0, min(ay2, by2) - max(ay1, by1))
    intersection = inter_w * inter_h
    area_a = max(int(region_a.get("w", 0)), 1) * max(int(region_a.get("h", 0)), 1)
    area_b = max(int(region_b.get("w", 0)), 1) * max(int(region_b.get("h", 0)), 1)
    union = max(area_a + area_b - intersection, 1)
    return intersection / union


def quantize_region(region: dict[str, Any], *, video_meta: dict[str, Any]) -> dict[str, Any]:
    snapped = dict(region)
    snapped["x"] = max(int(round(int(snapped.get("x", 0)) / 6.0) * 6), 0)
    snapped["y"] = max(int(round(int(snapped.get("y", 0)) / 6.0) * 6), 0)
    snapped["w"] = max(int(round(int(snapped.get("w", 0)) / 12.0) * 12), 1)
    snapped["h"] = max(int(round(int(snapped.get("h", 0)) / 6.0) * 6), 1)
    snapped["w"] = min(snapped["w"], max(int(video_meta["width"]) - snapped["x"], 1))
    snapped["h"] = min(snapped["h"], max(int(video_meta["height"]) - snapped["y"], 1))
    snapped["centerX"] = snapped["x"] + snapped["w"] // 2
    snapped["centerY"] = snapped["y"] + snapped["h"] // 2
    return snapped


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def cross_validate_regions(
    regions: list[dict[str, Any]],
    *,
    video_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    """Pass 2: Cross-validate detected regions.
    Filter out outlier detections whose position/size deviates significantly
    from the temporal cluster. Subtitles don't jump around — a region that's
    far from the majority is likely a false detection.
    """
    if len(regions) < 3:
        return regions

    def median_of(values: list[int]) -> int:
        return _median(values)

    med_x = median_of([int(r.get("x", 0)) for r in regions])
    med_y = median_of([int(r.get("y", 0)) for r in regions])
    med_w = median_of([int(r.get("w", 0)) for r in regions])
    med_h = median_of([int(r.get("h", 0)) for r in regions])
    med_center_x = med_x + med_w // 2
    med_center_y = med_y + med_h // 2

    # Stricter tolerances than before:
    # - Horizontal deviation: within 15% of video width or 1.5x median width
    # - Vertical deviation: within 0.12x video height (subtitle bands are tight)
    max_dev_x = max(int(video_meta["width"] * 0.15), int(med_w * 1.5), 30)
    max_dev_y = max(int(video_meta["height"] * 0.12), int(med_h * 1.2), 18)

    validated: list[dict[str, Any]] = []
    for region in regions:
        cx = int(region.get("centerX", int(region.get("x", 0)) + int(region.get("w", 0)) // 2))
        cy = int(region.get("centerY", int(region.get("y", 0)) + int(region.get("h", 0)) // 2))
        rw = int(region.get("w", 0))
        # Outlier: center too far from median OR width is 3x+ median (noise)
        if abs(cx - med_center_x) <= max_dev_x and abs(cy - med_center_y) <= max_dev_y and rw <= med_w * 4:
            validated.append(region)
        else:
            # Keep but mark as low-confidence fallback
            validated.append({**region, "_outlier": True})
    return validated


def consolidate_detected_regions(
    detected_regions: list[dict[str, Any]],
    *,
    video_meta: dict[str, Any],
) -> dict[str, Any] | None:
    if not detected_regions:
        return None
    if len(detected_regions) == 1:
        return quantize_region(detected_regions[0], video_meta=video_meta)

    # Pass 2: Cross-validate before consolidation
    validated = cross_validate_regions(detected_regions, video_meta=video_meta)
    non_outliers = [r for r in validated if not r.get("_outlier")]

    # Use median values as the anchor (more robust than highest-confidence)
    source = non_outliers if non_outliers else validated

    def med(values: list[int]) -> int:
        return _median(values)

    med_x = med([int(r.get("x", 0)) for r in source])
    med_y = med([int(r.get("y", 0)) for r in source])
    med_w = med([int(r.get("w", 0)) for r in source])
    med_h = med([int(r.get("h", 0)) for r in source])
    max_conf = max(float(r.get("confidence", 0.0)) for r in source)

    # Build anchor from median values
    anchor = {
        "x": med_x,
        "y": med_y,
        "w": med_w,
        "h": med_h,
        "centerX": med_x + med_w // 2,
        "centerY": med_y + med_h // 2,
        "confidence": max_conf,
    }

    # Stricter compatibility: IoU >= 0.3 AND closer spatial tolerances
    compatible: list[dict[str, Any]] = []
    for region in source:
        iou = region_iou(region, anchor)
        dx = abs(int(region.get("centerX", 0)) - anchor["centerX"])
        dy = abs(int(region.get("centerY", 0)) - anchor["centerY"])
        if iou >= 0.3 or (dx <= max(int(anchor["w"] * 0.22), 28) and dy <= max(int(anchor["h"] * 0.45), 16)):
            compatible.append(region)

    final_source = compatible if compatible else source

    merged = {
        "x": med([int(r.get("x", 0)) for r in final_source]),
        "y": med([int(r.get("y", 0)) for r in final_source]),
        "w": med([int(r.get("w", 0)) for r in final_source]),
        "h": med([int(r.get("h", 0)) for r in final_source]),
        "confidence": max(float(r.get("confidence", 0.0)) for r in final_source),
    }
    merged["centerX"] = merged["x"] + merged["w"] // 2
    merged["centerY"] = merged["y"] + merged["h"] // 2
    return quantize_region(merged, video_meta=video_meta)


def stabilize_region(candidate: dict[str, Any], previous: dict[str, Any], *, video_meta: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return quantize_region(candidate, video_meta=video_meta)
    center_dx = abs(int(candidate.get("centerX", 0)) - int(previous.get("centerX", 0)))
    center_dy = abs(int(candidate.get("centerY", 0)) - int(previous.get("centerY", 0)))
    size_dw = abs(int(candidate.get("w", 0)) - int(previous.get("w", 0)))
    size_dh = abs(int(candidate.get("h", 0)) - int(previous.get("h", 0)))
    iou = region_iou(candidate, previous)

    # Nếu box thay đổi cực kỳ ít (cả vị trí và kích thước), giữ nguyên box cũ để tránh rung giật
    if center_dx <= 12 and center_dy <= 8 and size_dw <= 18 and size_dh <= 12:
        return previous.copy()

    # Nếu box có thay đổi kích thước nhưng vị trí Y không đổi, ta ưu tiên giữ Y cũ, nhưng cho phép width thay đổi
    quantized = quantize_region(candidate, video_meta=video_meta)
    if center_dy <= 12 and size_dh <= 12:
        quantized["y"] = previous["y"]
        quantized["h"] = previous["h"]
        quantized["centerY"] = previous["centerY"]

    return quantized


def choose_cleanup_effect(region: dict[str, Any], *, video_meta: dict[str, Any]) -> str:
    confidence = float(region.get("confidence", 0.0))
    region_w = int(region.get("w", 0))
    region_h = int(region.get("h", 0))
    if confidence >= 0.3 and region_w <= int(video_meta["width"] * 0.72) and region_h <= int(video_meta["height"] * 0.09):
        return "blur"
    return "mask"


def choose_region_for_subtitle(subtitle: SubtitleLine, regions: list[dict[str, Any]]) -> dict[str, Any] | None:
    best_region: dict[str, Any] | None = None
    best_overlap = -1
    subtitle_start = int(subtitle.start_ms)
    subtitle_end = int(subtitle.end_ms)
    subtitle_mid = int((subtitle_start + subtitle_end) / 2)
    for region in regions:
        overlap = min(subtitle_end, int(region.get("endMs", 0))) - max(subtitle_start, int(region.get("startMs", 0)))
        if overlap > best_overlap:
            best_overlap = overlap
            best_region = region
    if best_region and best_overlap > 0:
        return best_region

    best_distance = None
    for region in regions:
        region_mid = int((int(region.get("startMs", 0)) + int(region.get("endMs", 0))) / 2)
        distance = abs(region_mid - subtitle_mid)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_region = region
    return best_region


def build_stable_subtitle_positions(
    subtitles: list[SubtitleLine],
    *,
    dynamic_regions: list[dict[str, Any]],
    fallback_region: dict[str, Any],
    video_meta: dict[str, Any],
) -> list[dict[str, int]]:
    fallback_center = {
        "centerX": int(fallback_region.get("x", 0)) + int(fallback_region.get("w", 0)) // 2,
        "centerY": int(fallback_region.get("y", 0)) + int(fallback_region.get("h", 0)) // 2,
    }
    previous = fallback_center.copy()
    positions: list[dict[str, int]] = []
    for subtitle in subtitles:
        region = choose_region_for_subtitle(subtitle, dynamic_regions) or fallback_region
        center_x = int(region.get("centerX", fallback_center["centerX"]))
        center_y = int(region.get("centerY", fallback_center["centerY"]))

        if abs(center_x - fallback_center["centerX"]) <= 72:
            center_x = fallback_center["centerX"]
        if abs(center_y - fallback_center["centerY"]) <= 24:
            center_y = fallback_center["centerY"]

        dx = abs(center_x - previous["centerX"])
        dy = abs(center_y - previous["centerY"])
        if dx <= 84:
            center_x = previous["centerX"]
        elif dx <= 144:
            center_x = int(round((previous["centerX"] * 3 + center_x) / 4))

        if dy <= 42:
            center_y = previous["centerY"]
        elif dy <= 96:
            center_y = int(round((previous["centerY"] * 3 + center_y) / 4))

        center_x = max(min(snap_axis(center_x, 6), int(video_meta["width"])), 0)
        center_y = max(min(snap_axis(center_y, 6), int(video_meta["height"])), 0)
        stable_position = {"centerX": center_x, "centerY": center_y}
        positions.append(stable_position)
        previous = stable_position
    return positions


def build_dynamic_subtitle_regions(
    video_path: Path,
    *,
    video_meta: dict[str, Any],
    subtitles: list[SubtitleLine],
    fallback_region: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, int]]]:
    if not subtitles:
        fallback_position = {
            "centerX": fallback_region.get("x", 0) + fallback_region.get("w", 0) // 2,
            "centerY": fallback_region.get("y", 0) + fallback_region.get("h", 0) // 2,
        }
        return [], [fallback_position]

    sample_width = min(480, max(240, int(video_meta["width"] * 0.33)))
    sample_height = max(int(video_meta["height"] * sample_width / max(video_meta["width"], 1)), 180)
    cache: dict[int, dict[str, Any]] = {}
    dynamic_regions: list[dict[str, Any]] = []
    fallback_position_region = {
        **fallback_region,
        "centerX": fallback_region.get("x", 0) + fallback_region.get("w", 0) // 2,
        "centerY": fallback_region.get("y", 0) + fallback_region.get("h", 0) // 2,
        "confidence": 0.0,
        "detected": False,
    }
    fallback_anchor_region = quantize_region(fallback_position_region, video_meta=video_meta)
    previous_detected_region: dict[str, Any] | None = None

    for index, subtitle in enumerate(subtitles):
        sub_start = int(subtitle.start_ms)
        sub_end = int(subtitle.end_ms)
        subtitle_duration = max(sub_end - sub_start, 1)

        # Sample only a few points per subtitle; frame extraction is one of the
        # most expensive parts of render when cleanup is enabled.
        num_samples = min(max(int(DUB_SUBTITLE_REGION_SAMPLES), 1), 8)
        sample_points = set()
        if num_samples == 1:
            fractions = [0.5]
        elif num_samples == 2:
            fractions = [0.25, 0.75]
        else:
            fractions = [i / max(num_samples - 1, 1) for i in range(num_samples)]
        for frac in fractions:
            pt = int(sub_start + frac * subtitle_duration)
            sample_points.add(pt)

        detected_regions: list[dict[str, Any]] = []
        for sample_point in sorted(sample_points):
            # Coarser cache key (round to nearest 150ms) to avoid duplicate extraction
            sample_key = int(round(sample_point / 150.0) * 150)
            if sample_key not in cache:
                try:
                    frame = extract_gray_frame(video_path, sample_key, sample_width, sample_height)
                    cache[sample_key] = detect_subtitle_region_in_frame(
                        frame,
                        sample_width=sample_width,
                        sample_height=sample_height,
                        video_meta=video_meta,
                        fallback_region=fallback_region,
                    )
                except Exception:
                    cache[sample_key] = fallback_position_region.copy()
            region = cache[sample_key]
            if subtitle_region_detected(region):
                detected_regions.append(quantize_region(region, video_meta=video_meta))

        region: dict[str, Any] | None = None
        if detected_regions:
            # Pass 2: Cross-validate detections (removes temporal outliers)
            validated = cross_validate_regions(detected_regions, video_meta=video_meta)
            non_outliers = [r for r in validated if not r.get("_outlier")]
            source = non_outliers if non_outliers else detected_regions
            region = consolidate_detected_regions(source, video_meta=video_meta)
        elif previous_detected_region is not None:
            region = previous_detected_region.copy()
        elif subtitle_region_detected(fallback_anchor_region):
            region = fallback_anchor_region.copy()

        if region is None:
            region = fallback_anchor_region.copy()
            region["detected"] = True
            region["confidence"] = SOURCE_SUBTITLE_DETECTION_CONFIDENCE

        if detected_regions and previous_detected_region is not None:
            big_vertical_jump = abs(int(region.get("centerY", 0)) - int(previous_detected_region.get("centerY", 0))) > int(video_meta["height"] * 0.18)
            big_horizontal_jump = abs(int(region.get("centerX", 0)) - int(previous_detected_region.get("centerX", 0))) > int(video_meta["width"] * 0.16)
            if (
                previous_detected_region.get("confidence", 0.0) > 0.0
                and (big_vertical_jump or big_horizontal_jump)
                and float(region.get("confidence", 0.0)) < float(previous_detected_region.get("confidence", 0.0)) * 1.55
            ):
                region = previous_detected_region
            region = stabilize_region(region, previous_detected_region, video_meta=video_meta)
        elif detected_regions:
            region = quantize_region(region, video_meta=video_meta)

        region["detected"] = True
        region["confidence"] = round(max(float(region.get("confidence", 0.0)), SOURCE_SUBTITLE_DETECTION_CONFIDENCE), 4)

        # Apply minimum padding — just enough to avoid cutting off the edges of subtitle text
        padded_region = expand_subtitle_region(region, video_meta=video_meta)
        padded_region["centerX"] = padded_region["x"] + padded_region["w"] // 2
        padded_region["centerY"] = padded_region["y"] + padded_region["h"] // 2

        # Temporal padding: lead/trail around the subtitle period
        previous_end = int(subtitles[index - 1].end_ms) if index > 0 else 0
        next_start = int(subtitles[index + 1].start_ms) if index + 1 < len(subtitles) else int(subtitle.end_ms)
        gap_before = max(sub_start - previous_end, 0)
        gap_after = max(next_start - sub_end, 0)
        lead_ms = min(max(int(gap_before * 0.65), 120), 360)
        trail_ms = min(max(int(gap_after * 0.65), 160), 520)
        padded_region["startMs"] = max(sub_start - lead_ms, 0)
        padded_region["endMs"] = max(sub_end + trail_ms, padded_region["startMs"] + 120)
        padded_region["cleanupEffect"] = choose_cleanup_effect(padded_region, video_meta=video_meta)
        padded_region["detected"] = True
        dynamic_regions.append(padded_region)
        previous_detected_region = region.copy()

    subtitle_positions = build_stable_subtitle_positions(
        subtitles,
        dynamic_regions=dynamic_regions,
        fallback_region=fallback_region,
        video_meta=video_meta,
    )
    return dynamic_regions, subtitle_positions

