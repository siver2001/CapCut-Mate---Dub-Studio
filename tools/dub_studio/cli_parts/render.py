from __future__ import annotations

import copy
import inspect

from .common import *
from .analysis import (
    analyze_with_local_whisper,
    analyze_with_whisperx,
    build_dynamic_subtitle_regions,
    build_speakers,
    detect_source_language,
    extract_speaker_samples,
    is_valtec_reference_voice,
    is_valtec_voice_preset,
    is_vieneu_voice_preset,
    resolve_tts_output_extension,
    resolve_valtec_reference_audio,
    resolve_voice_preset,
    subtitle_region_detected,
    subtitles_from_analysis_segments,
    build_stable_subtitle_positions,
)
from .audio import (
    create_dub_audio,
    create_final_audio,
    create_intro_audio,
    estimate_tts_text_profile,
    extract_video_clip,
    normalize_audio_mix_mode,
    prepare_background_audio_track,
    synthesize_timed_tts_clip,
    synthesize_tts,
)
from .runtime import ensure_valtec_runtime, ensure_vieneu_runtime, prepare_runtime
from .translation import (
    build_intro_hook_text,
    build_intro_hook_text_with_context,
    build_structured_intro_hook_text,
    generate_intro_hook_via_llama_cpp,
    generate_intro_hook_via_ollama,
    select_intro_hook_window,
    translate_segments,
)
from ..subtitle_utils import renumber_subtitle_timeline
from ..tts.text import sanitize_for_tts_or_raise

def stable_video_codec() -> tuple[str, list[str]]:
    # Favor a faster default preset for interactive dubbing/export iterations.
    return "libx264", [
        "-preset",
        VIDEO_X264_PRESET,
        "-crf",
        str(VIDEO_X264_CRF),
        "-pix_fmt",
        "yuv420p",
    ]


@lru_cache(maxsize=1)
def ffmpeg_encoders() -> str:
    try:
        return run_output(["ffmpeg", "-hide_banner", "-encoders"])
    except Exception:
        return ""


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def requested_video_codec_mode() -> str:
    mode = os.environ.get("CAPCUT_VIDEO_CODEC_MODE", "").strip().lower()
    if mode in {"gpu_preferred", "cpu_stable"}:
        return mode
    if env_flag("CAPCUT_ENABLE_NVENC"):
        return "gpu_preferred"
    return "gpu_preferred"


@lru_cache(maxsize=1)
def can_use_nvenc() -> bool:
    if "h264_nvenc" not in ffmpeg_encoders():
        return False
    try:
        # Some ffmpeg builds list NVENC even when the current machine cannot use
        # it. Run a tiny smoke test before opting into GPU encoding.
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=256x256:r=1",
                "-frames:v",
                "1",
                "-an",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                "-",
            ],
            cwd=ROOT,
            capture_output=True,
        )
        return True
    except Exception:
        return False


def normalize_source_subtitle_cleanup_mode(mode: Any) -> str:
    if mode is None:
        return "localized_blur"
    normalized = str(mode).strip().lower()
    if normalized in {"", "none", "off", "disabled", "disable", "false", "0", "no"}:
        return "none"
    if normalized == "localized_mask":
        return "localized_mask"
    return "localized_blur"


def source_subtitles_detected(
    subtitle_region: dict[str, Any] | None,
    dynamic_regions: list[dict[str, Any]] | None = None,
) -> bool:
    if dynamic_regions:
        return any(subtitle_region_detected(region) for region in dynamic_regions)
    if subtitle_region_detected(subtitle_region):
        return True
    return False


def filter_dynamic_cleanup_regions(
    dynamic_regions: list[dict[str, Any]] | None,
    *,
    anchor_region: dict[str, Any] | None,
    video_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    regions = [region for region in (dynamic_regions or []) if int(region.get("w", 0)) > 0 and int(region.get("h", 0)) > 0]
    if not regions or not anchor_region:
        return regions
    anchor_w = int(anchor_region.get("w", 0))
    anchor_h = int(anchor_region.get("h", 0))
    if anchor_w <= 0 or anchor_h <= 0:
        return regions
    anchor_center_x = int(anchor_region.get("x", 0)) + anchor_w // 2
    anchor_center_y = int(anchor_region.get("y", 0)) + anchor_h // 2
    max_center_dx = max(int(anchor_w * 0.38), int(video_meta["width"] * 0.1), 36)
    max_center_dy = max(int(anchor_h * 2.0), int(video_meta["height"] * 0.05), 28)
    filtered: list[dict[str, Any]] = []
    for region in regions:
        center_x = int(region.get("centerX", int(region.get("x", 0)) + int(region.get("w", 0)) // 2))
        center_y = int(region.get("centerY", int(region.get("y", 0)) + int(region.get("h", 0)) // 2))
        if abs(center_x - anchor_center_x) <= max_center_dx and abs(center_y - anchor_center_y) <= max_center_dy:
            filtered.append(region)
    return filtered


def resolve_source_subtitle_cleanup_mode(
    requested_mode: Any,
    *,
    subtitle_region: dict[str, Any] | None,
    dynamic_regions: list[dict[str, Any]] | None = None,
) -> str:
    normalized_mode = normalize_source_subtitle_cleanup_mode(requested_mode)
    if normalized_mode == "none":
        return "none"
    if not source_subtitles_detected(subtitle_region, dynamic_regions):
        return "none"
    return normalized_mode


def choose_video_codec() -> tuple[str, list[str]]:
    mode = requested_video_codec_mode()
    if mode == "cpu_stable":
        return stable_video_codec()
    if can_use_nvenc():
        return "h264_nvenc", [
            "-preset",
            VIDEO_NVENC_PRESET,
            "-rc",
            "vbr",
            "-cq",
            str(VIDEO_NVENC_CQ),
            "-pix_fmt",
            "yuv420p",
        ]
    return stable_video_codec()


def expand_cleanup_region_for_render(
    region: dict[str, Any],
    *,
    video_meta: dict[str, Any],
    subtitle_preset: dict[str, Any],
) -> dict[str, int]:
    width = int(video_meta.get("width") or 1080)
    height = int(video_meta.get("height") or 1920)
    region_w = max(int(region.get("w", 0)), 1)
    region_h = max(int(region.get("h", 0)), 1)
    center_x = int(region.get("centerX", int(region.get("x", 0)) + region_w // 2))
    center_y = int(region.get("centerY", int(region.get("y", 0)) + region_h // 2))

    # Expand width and height slightly by adding padding
    padding_w = max(int(region_w * 0.15), 30)
    padding_h = max(int(region_h * 0.07), 8)
    
    expanded_w = min(width, region_w + padding_w)
    expanded_h = min(height, region_h + padding_h)

    # Center the expanded box on the original region
    x = max(min(center_x - expanded_w // 2, width - expanded_w), 0)
    y = max(min(center_y - expanded_h // 2, height - expanded_h), 0)

    return {"x": x, "y": y, "w": expanded_w, "h": expanded_h}


def burn_subtitles(
    *,
    video_path: Path,
    audio_path: Path,
    subtitles_path: Path,
    output_path: Path,
    cleanup_mode: str,
    subtitle_region: dict[str, Any],
    subtitle_preset: dict[str, Any],
    dynamic_regions: list[dict[str, Any]] | None = None,
    use_ass: bool = False,
    output_ratio: str = "original",
) -> None:
    codec, codec_args = choose_video_codec()
    source_video_meta = get_video_meta(video_path)
    target_duration_seconds = max(ffprobe_duration_ms(video_path) / 1000, 0.1)
    font_size = effective_ass_font_size(subtitle_preset, source_video_meta)
    effective_region = resolve_subtitle_region_for_position(
        video_meta=source_video_meta,
        subtitle_region=subtitle_region,
        subtitle_preset=subtitle_preset,
    )
    margin_v = effective_ass_margin_v(subtitle_preset, source_video_meta)
    cleanup_blur_strength = max(
        2,
        min(
            int(subtitle_preset.get("cleanupBlurStrength", subtitle_region.get("blurStrength", 10))),
            24,
        ),
    )
    blur_filter = (
        f"boxblur=luma_radius={cleanup_blur_strength}:luma_power=1,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.58:t=fill"
    )
    font_name = subtitle_preset.get("assFontName") or subtitle_preset.get("fontFamilyName") or "Arial"
    primary_color = subtitle_preset.get("assPrimaryColor") or "&H0038D8FF"
    outline_color = subtitle_preset.get("assOutlineColor") or "&H00000000"
    outline = effective_ass_outline(int(subtitle_preset.get("strokeWidth", 2)), source_video_meta)
    box_enabled = bool(subtitle_preset.get("boxEnabled", False))
    box_layout_mode = str(subtitle_preset.get("boxLayoutMode", "line") or "line").strip().lower()
    use_unified_box = box_enabled and box_layout_mode == "unified"
    box_fill_color = subtitle_preset.get("assBoxFillColor") or hex_to_ass_color(
        subtitle_preset.get("boxFillColor", "#77b8ee"),
        float(subtitle_preset.get("boxFillOpacity", 0.86)),
    )
    box_border_color = subtitle_preset.get("assBoxBorderColor") or hex_to_ass_color(
        subtitle_preset.get("boxBorderColor", "#3b82f6"),
        float(subtitle_preset.get("boxBorderOpacity", 1.0)),
    )
    box_shadow = (
        effective_ass_outline(
            max(
                int(
                    round(
                        (int(subtitle_preset.get("boxPaddingX", 24)) + int(subtitle_preset.get("boxPaddingY", 12))) / 10
                    )
                ),
                2,
            ),
            source_video_meta,
        )
        if use_unified_box
        else 0
    )

    if use_ass:
        subtitles_filter = f"ass={subtitles_path.relative_to(ROOT).as_posix()}"
    else:
        subtitles_filter = (
            f"subtitles={subtitles_path.relative_to(ROOT).as_posix()}:"
            f"force_style='FontName={font_name},PrimaryColour={primary_color},"
            f"OutlineColour={outline_color if use_unified_box else box_border_color if box_enabled else outline_color},"
            f"BorderStyle={3 if box_enabled else 1},"
            f"Outline={effective_ass_outline(int(subtitle_preset.get('boxPaddingX', 24)), source_video_meta) if box_enabled else outline},Shadow={box_shadow},"
            f"FontSize={font_size},BackColour={box_fill_color if box_enabled else '&H00000000'},"
            f"MarginV={margin_v},Alignment=2'"
        )

    cleanup_region = expand_cleanup_region_for_render(
        effective_region,
        video_meta=source_video_meta,
        subtitle_preset=subtitle_preset,
    )
    region_x = int(cleanup_region.get("x", 0))
    region_y = int(cleanup_region.get("y", 0))
    region_w = int(cleanup_region.get("w", 0))
    region_h = int(cleanup_region.get("h", 0))

    dynamic_regions = [region for region in (dynamic_regions or []) if int(region.get("w", 0)) > 0 and int(region.get("h", 0)) > 0]

    if dynamic_regions:
        if cleanup_mode == "localized_blur":
            drawbox_chain = ",".join(
                [
                    (
                        lambda cleanup_region: (
                            "drawbox="
                            f"x={cleanup_region['x']}:"
                            f"y={cleanup_region['y']}:"
                            f"w={cleanup_region['w']}:"
                            f"h={cleanup_region['h']}:"
                            "color=white:t=fill:"
                            f"enable='between(t,{max(int(region.get('startMs', 0)), 0) / 1000:.3f},{max(int(region.get('endMs', 0)), 0) / 1000:.3f})'"
                        )
                    )(
                        expand_cleanup_region_for_render(
                            region,
                            video_meta=source_video_meta,
                            subtitle_preset=subtitle_preset,
                        )
                    )
                    for region in dynamic_regions
                ]
            )
            video_filter = (
                "[0:v]split=3[orig][blur_src][mask_src];"
                f"[blur_src]{blur_filter}[blurred];"
                f"[mask_src]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill,{drawbox_chain}[mask];"
                "[orig][blurred][mask]maskedmerge[merged];"
                f"[merged]{subtitles_filter}[vout]"
            )
            filter_arg = "-filter_complex"
            video_map = "[vout]"
        elif cleanup_mode == "localized_mask":
            drawbox_chain = ",".join(
                [
                    (
                        lambda cleanup_region: (
                            "drawbox="
                            f"x={cleanup_region['x']}:"
                            f"y={cleanup_region['y']}:"
                            f"w={cleanup_region['w']}:"
                            f"h={cleanup_region['h']}:"
                            "color=black@0.78:t=fill:"
                            f"enable='between(t,{max(int(region.get('startMs', 0)), 0) / 1000:.3f},{max(int(region.get('endMs', 0)), 0) / 1000:.3f})'"
                        )
                    )(
                        expand_cleanup_region_for_render(
                            region,
                            video_meta=source_video_meta,
                            subtitle_preset=subtitle_preset,
                        )
                    )
                    for region in dynamic_regions
                ]
            )
            video_filter = f"{drawbox_chain},{subtitles_filter}" if drawbox_chain else subtitles_filter
            filter_arg = "-vf"
            video_map = "0:v:0"
        else:
            video_filter = subtitles_filter
            filter_arg = "-vf"
            video_map = "0:v:0"
    else:
        if cleanup_mode == "localized_blur":
            video_filter = (
                "[0:v]split=2[base][masksrc];"
                f"[masksrc]crop=w={region_w}:h={region_h}:x={region_x}:y={region_y},"
                f"{blur_filter}[mask];"
                f"[base][mask]overlay={region_x}:{region_y}[clean];"
                f"[clean]{subtitles_filter}[vout]"
            )
            filter_arg = "-filter_complex"
            video_map = "[vout]"
        elif cleanup_mode == "localized_mask":
            video_filter = f"drawbox=x={region_x}:y={region_y}:w={region_w}:h={region_h}:color=black@0.78:t=fill,{subtitles_filter}"
            filter_arg = "-vf"
            video_map = "0:v:0"
        else:
            video_filter = subtitles_filter
            filter_arg = "-vf"
            video_map = "0:v:0"

    command = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", video_map,
        "-map", "1:a:0",
    ]
    
    watermark_opts = subtitle_preset.get("watermarkOptions")
    if watermark_opts and watermark_opts.get("enabled"):
        filter_arg, video_filter, video_map = apply_watermark_to_ffmpeg_command(
            command, filter_arg, video_filter, video_map, watermark_opts, get_video_meta(video_path)
        )
        command[command.index("-map") + 1] = video_map

    if output_ratio and output_ratio != "original":
        filter_arg, video_filter, video_map = apply_aspect_ratio_to_ffmpeg_command(
            filter_arg, video_filter, video_map, output_ratio
        )
        command[command.index("-map") + 1] = video_map
        
    temp_script_path: Path | None = None
    if filter_arg == "-filter_complex" and len(video_filter) > 3500:
        temp_script_path = output_path.with_suffix(".ffmpeg-filter.txt")
        temp_script_path.write_text(video_filter, encoding="utf-8")
        command.extend(["-filter_complex_script", str(temp_script_path)])
    else:
        command.extend([filter_arg, video_filter])
    command.extend(
        [
            "-af",
            f"apad,atrim=0:{target_duration_seconds:.3f},{stable_audio_filter_chain()}",
            "-c:v",
            codec,
            *codec_args,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-t",
            f"{target_duration_seconds:.3f}",
            str(output_path),
        ]
    )
    try:
        run(command, cwd=ROOT)
    finally:
        if temp_script_path and temp_script_path.exists():
            temp_script_path.unlink(missing_ok=True)


def invoke_create_final_audio_compat(
    input_path: Path,
    dub_audio_path: Path,
    mixed_audio_path: Path,
    *,
    audio_mix_mode: str,
    keep_original_audio: bool,
    background_audio_path: Path | None,
    background_music_path: Path | None = None,
    background_music_volume: float = 0.0,
) -> None:
    kwargs = {
        "audio_mix_mode": audio_mix_mode,
        "keep_original_audio": keep_original_audio,
        "background_audio_path": background_audio_path,
        "background_music_path": background_music_path,
        "background_music_volume": background_music_volume,
    }
    try:
        signature = inspect.signature(create_final_audio)
    except Exception:
        signature = None
    if signature is not None:
        accepts_var_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
        )
        if not accepts_var_kwargs:
            kwargs = {name: value for name, value in kwargs.items() if name in signature.parameters}
    create_final_audio(
        input_path,
        dub_audio_path,
        mixed_audio_path,
        **kwargs,
    )


def render_intro_hook(
    *,
    input_path: Path,
    video_meta: dict[str, Any],
    segments: list[dict[str, Any]],
    source_language: str,
    voice_mapping: dict[str, str],
    subtitle_region: dict[str, Any],
    subtitle_preset: dict[str, Any],
    subtitle_enabled: bool,
    cleanup_mode: str,
    intro_hook: dict[str, Any],
    timing_mode: str,
    dirs: dict[str, Path],
    background_music_path: Path | None = None,
    background_music_volume: float = 0.0,
    dynamic_regions: list[dict[str, Any]] | None = None,
    output_ratio: str = "original",
) -> dict[str, Any]:
    video_duration_ms = int(video_meta.get("durationMs", 0))
    clip_window = select_intro_hook_window(
        segments,
        video_duration_ms=video_duration_ms,
        desired_clip_ms=int(intro_hook.get("clipDurationMs", 13000)),
    )
    emit_progress(phase="render", step="intro_hook", progress=0.86, message="Đang soạn lời thoại intro (AI)...")
    intro_text = build_intro_hook_text_with_context(
        clip_window["segments"],
        source_language=source_language,
        clip_duration_ms=clip_window["durationMs"],
    )
    tts_profile = estimate_tts_text_profile(intro_text)
    remaining_source_ms = max(video_duration_ms - clip_window["startMs"], clip_window["durationMs"])
    max_intro_duration_ms = min(max(clip_window["durationMs"] + 6000, 24000), remaining_source_ms)
    desired_intro_duration_ms = min(
        max(
            clip_window["durationMs"],
            int(tts_profile.get("expectedSeconds", 0.0) * 1000) + 900,
        ),
        max_intro_duration_ms,
    )
    emit_progress(phase="render", step="intro_hook", progress=0.87, message="Đang tạo giọng nói intro (TTS)...")
    intro_voice = intro_hook.get("voice") or voice_mapping.get("speaker_1") or DEFAULT_VOICES[0]
    intro_rate_delta_percent = int(intro_hook.get("voiceRateDeltaPercent") or 0)
    clip_path = dirs["render"] / "intro_hook_source.mp4"
    mixed_intro_audio = dirs["audio"] / "intro_hook_audio.wav"
    intro_srt_path = dirs["render"] / "intro_hook.srt"
    intro_ass_path = dirs["render"] / "intro_hook.ass"
    teaser_output_path = dirs["render"] / "intro_hook_rendered.mp4"

    fitted_intro_voice, intro_clip_ms, intro_rate, _, _, _ = synthesize_timed_tts_clip(
        index=0,
        speaker_id="intro_hook",
        voice=intro_voice,
        translated=intro_text,
        source_text=intro_text,
        delivery="excited",
        target_ms=max(desired_intro_duration_ms - 140, 1200),
        timing_mode=timing_mode,
        tts_dir=dirs["tts"],
        intro=True,
        rate_delta_percent=intro_rate_delta_percent,
    )
    actual_intro_duration_ms = min(
        max(
            clip_window["durationMs"],
            desired_intro_duration_ms,
            int(intro_clip_ms) + 380,
        ),
        remaining_source_ms,
    )
    extract_video_clip(input_path, clip_path, clip_window["startMs"], actual_intro_duration_ms)
    create_intro_audio(
        video_clip_path=clip_path,
        intro_voice_path=fitted_intro_voice,
        output_path=mixed_intro_audio,
        has_audio=bool(video_meta.get("hasAudio")),
        use_background_audio=bool(intro_hook.get("useBackgroundAudio", True)),
        background_volume=float(intro_hook.get("backgroundVolume", 0.08)),
        background_music_path=background_music_path,
        background_music_volume=background_music_volume,
    )

    if subtitle_enabled:
        intro_subtitles = create_display_subtitles(
            [
                {
                    "translatedText": intro_text,
                    "startMs": 0,
                    "endMs": int(intro_clip_ms),
                }
            ],
            max_words=int(subtitle_preset.get("maxWordsPerChunk", 5)),
            max_chars=int(subtitle_preset.get("maxCharsPerChunk", 22)),
            punctuation_aware=bool(subtitle_preset.get("punctuationAwareSplit", True)),
        )
        if normalize_source_subtitle_cleanup_mode(cleanup_mode) != "none":
            if dynamic_regions:
                teaser_start = clip_window["startMs"]
                teaser_end = teaser_start + actual_intro_duration_ms
                
                intro_dynamic_regions = []
                for r in dynamic_regions:
                    if r.get("endMs", 0) <= teaser_start or r.get("startMs", 0) >= teaser_end:
                        continue
                    r_shifted = r.copy()
                    r_shifted["startMs"] = max(0, int(r.get("startMs", 0)) - teaser_start)
                    r_shifted["endMs"] = min(actual_intro_duration_ms, int(r.get("endMs", 0)) - teaser_start)
                    intro_dynamic_regions.append(r_shifted)
            else:
                intro_dynamic_regions, _ = build_dynamic_subtitle_regions(
                    clip_path,
                    video_meta=video_meta,
                    subtitles=intro_subtitles,
                    fallback_region=subtitle_region,
                )
            
            if any(r.get("detected") for r in intro_dynamic_regions):
                intro_dynamic_regions = [r for r in intro_dynamic_regions if r.get("detected")]
            else:
                # Không phát hiện thấy sub cũ nào trong toàn bộ video -> Không che
                intro_dynamic_regions = []
        else:
            intro_dynamic_regions = []
        intro_positions = build_stable_subtitle_positions(
            intro_subtitles,
            dynamic_regions=intro_dynamic_regions,
            fallback_region=subtitle_region,
            video_meta=video_meta,
        )
        intro_ass_path.write_text(
            compose_ass(
                intro_subtitles,
                video_meta=video_meta,
                subtitle_preset=subtitle_preset,
                subtitle_positions=intro_positions,
            ),
            encoding="utf-8",
        )
        intro_srt_path.write_text(compose_srt(intro_subtitles), encoding="utf-8")
        burn_subtitles(
            video_path=clip_path,
            audio_path=mixed_intro_audio,
            subtitles_path=intro_ass_path,
            output_path=teaser_output_path,
            cleanup_mode=cleanup_mode,
            subtitle_region=subtitle_region,
            subtitle_preset=subtitle_preset,
            dynamic_regions=intro_dynamic_regions,
            use_ass=True,
            output_ratio=output_ratio,
        )
    else:
        mux_video_with_audio(video_path=clip_path, audio_path=mixed_intro_audio, output_path=teaser_output_path, output_ratio=output_ratio)
    return {
        "enabled": True,
        "text": intro_text,
        "videoPath": str(teaser_output_path),
        "sourceStartMs": clip_window["startMs"],
        "sourceEndMs": min(clip_window["startMs"] + actual_intro_duration_ms, max(video_duration_ms, actual_intro_duration_ms)),
        "durationMs": actual_intro_duration_ms,
        "voice": intro_voice,
        "rate": intro_rate,
    }


def concat_rendered_videos(intro_video_path: Path, main_video_path: Path, output_path: Path) -> None:
    codec, codec_args = choose_video_codec()
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(intro_video_path),
            "-i",
            str(main_video_path),
            "-filter_complex",
            "[0:v:0][0:a:0][1:v:0][1:a:0]concat=n=2:v=1:a=1[v][acat];"
            f"[acat]{stable_audio_filter_chain()}[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            codec,
            *codec_args,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        cwd=ROOT,
    )

def concat_ending_video_safe(main_video_path: Path, ending_video_path: Path, output_path: Path) -> None:
    codec, codec_args = choose_video_codec()
    try:
        from .common import get_video_meta
        meta = get_video_meta(main_video_path)
        w = int(meta.get("width", 1080))
        h = int(meta.get("height", 1920))
        if w % 2 != 0: w += 1
        if h % 2 != 0: h += 1
    except Exception:
        w, h = 1080, 1920

    run(
        [
            "ffmpeg",
            "-y",
            "-i", str(main_video_path),
            "-i", str(ending_video_path),
            "-filter_complex",
            f"[1:v:0]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1[v1];"
            f"[0:v:0][0:a:0][v1][1:a:0]concat=n=2:v=1:a=1[v][acat];"
            f"[acat]{stable_audio_filter_chain()}[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", codec, *codec_args,
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ],
        cwd=ROOT,
    )


def finalize_main_render_output(main_render_path: Path, final_output_path: Path) -> Path:
    if final_output_path != main_render_path:
        final_output_path.unlink(missing_ok=True)
        main_render_path.replace(final_output_path)
        return final_output_path
    return main_render_path


def apply_watermark_to_ffmpeg_command(
    command: list[str],
    filter_arg: str,
    video_filter: str,
    video_map: str,
    watermark_options: dict[str, Any] | None,
    video_meta: dict[str, Any] | None
) -> tuple[str, str, str]:
    if not watermark_options or not watermark_options.get("enabled") or not watermark_options.get("path"):
        return filter_arg, video_filter, video_map
        
    watermark_path = Path(watermark_options["path"])
    if not watermark_path.exists():
        return filter_arg, video_filter, video_map
    # Actually, command input index calculation is safer if we just count '-i'
    input_count = command.count("-i")
    watermark_idx = input_count
    command.insert(command.index("-map"), "-i")
    command.insert(command.index("-map"), str(watermark_path))
    
    scale_factor = float(watermark_options.get("scale", 0.15))
    video_width = int(video_meta.get("width", 1080)) if video_meta else 1080
    wm_w = max(10, int(video_width * scale_factor))
    
    pos = watermark_options.get("position", "top-right")
    margin = 10
    if pos == "top-left":
        overlay_pos = f"{margin}:{margin}"
    elif pos == "top-right":
        overlay_pos = f"W-w-{margin}:{margin}"
    elif pos == "bottom-left":
        overlay_pos = f"{margin}:H-h-{margin}"
    else: # bottom-right
        overlay_pos = f"W-w-{margin}:H-h-{margin}"

    wm_filter = f"[{watermark_idx}:v]scale={wm_w}:-1,format=rgba[wm];"
    
    if filter_arg == "-vf":
        # Convert -vf to -filter_complex
        filter_arg = "-filter_complex"
        if video_map == "0:v:0":
            # No existing filter_complex, just apply to 0:v:0
            video_filter = f"{wm_filter}[0:v:0][wm]overlay={overlay_pos}[vout]"
        else:
            # -vf with an output? Unlikely. But if so:
            video_filter = f"[0:v:0]{video_filter}[base];{wm_filter}[base][wm]overlay={overlay_pos}[vout]"
        video_map = "[vout]"
    else:
        # Already -filter_complex
        # We need to take the output map, overlay watermark, and output a new map
        old_out = video_map.strip("[]")
        video_filter = f"{video_filter};{wm_filter}[{old_out}][wm]overlay={overlay_pos}[vout_wm]"
        video_map = "[vout_wm]"
        
    return filter_arg, video_filter, video_map

def apply_aspect_ratio_to_ffmpeg_command(
    filter_arg: str,
    video_filter: str,
    video_map: str,
    output_ratio: str
) -> tuple[str, str, str]:
    if output_ratio == "original" or not output_ratio:
        return filter_arg, video_filter, video_map
    
    is_dynamic = output_ratio.endswith("_dynamic")
    base_ratio = output_ratio.replace("_dynamic", "")
    
    ratio_map = {
        "9:16": (9, 16),
        "16:9": (16, 9),
        "1:1": (1, 1),
    }
    
    if is_dynamic:
        num, den = ratio_map.get(base_ratio, (9, 16))
        A = num / den
        # We calculate the padded width/height dynamically based on iw/ih
        pad_filter = f"pad='ceil(max(iw, ih*({A}))/2)*2':'ceil(max(ih, iw/({A}))/2)*2':(ow-iw)/2:(oh-ih)/2:black"
        scale_pad_filter = pad_filter
    else:
        fixed_ratio_map = {
            "9:16": ("1080", "1920"),
            "16:9": ("1920", "1080"),
            "1:1": ("1080", "1080"),
        }
        target_w, target_h = fixed_ratio_map.get(base_ratio, ("1080", "1920"))
        scale_pad_filter = f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
    
    if filter_arg == "-vf":
        video_filter = f"{video_filter},{scale_pad_filter}"
    else:
        old_out = video_map.strip("[]")
        video_filter = f"{video_filter};[{old_out}]{scale_pad_filter}[vout_ratio]"
        video_map = "[vout_ratio]"
        
    return filter_arg, video_filter, video_map

def mux_video_with_audio(
    *, 
    video_path: Path, 
    audio_path: Path, 
    output_path: Path,
    watermark_options: dict[str, Any] | None = None,
    video_meta: dict[str, Any] | None = None,
    output_ratio: str = "original",
) -> None:
    codec, codec_args = choose_video_codec()
    target_duration_seconds = max(ffprobe_duration_ms(video_path) / 1000, 0.1)
    command = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0"
    ]
    
    filter_arg = "-vf"
    video_filter = "null"
    video_map = "0:v:0"
    
    if watermark_options and watermark_options.get("enabled"):
        filter_arg, video_filter, video_map = apply_watermark_to_ffmpeg_command(
            command, filter_arg, video_filter, video_map, watermark_options, video_meta
        )

    if output_ratio and output_ratio != "original":
        filter_arg, video_filter, video_map = apply_aspect_ratio_to_ffmpeg_command(
            filter_arg, video_filter, video_map, output_ratio
        )
        
    if video_filter != "null":
        map_idx = command.index("-map")
        command[map_idx+1] = video_map
        command.insert(map_idx, video_filter)
        command.insert(map_idx, filter_arg)
        
    command.extend([
        "-af",
        f"apad,atrim=0:{target_duration_seconds:.3f},{stable_audio_filter_chain()}",
        "-c:v", codec, *codec_args,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-t", f"{target_duration_seconds:.3f}",
        str(output_path),
    ])
    run(command, cwd=ROOT)


def apply_sticker_overlay(
    input_video_path: Path,
    output_video_path: Path,
    sticker_options: dict[str, Any],
    scale: float = 1.0,
    transform_x: float = 0.0,
    transform_y: float = -0.3,
) -> Path:
    """
    Overlay a sticker (image/GIF) on top of a video using ffmpeg.

    Args:
        input_video_path: Path to the input video (with subtitles already burned).
        output_video_path: Path for the output video with sticker overlay.
        sticker_options: Dict with sticker data (image_url, sticker_id, etc.).
        scale: Sticker scale factor (default 1.0).
        transform_x: X offset in normalized coordinates (-1 to 1).
        transform_y: Y offset in normalized coordinates (-1 to 1).

    Returns:
        Path to the output video.
    """
    image_url = str(sticker_options.get("image_url") or "").strip()
    if not image_url:
        logger.warning("apply_sticker_overlay: no image_url in sticker_options")
        if input_video_path != output_video_path:
            import shutil
            shutil.copy2(input_video_path, output_video_path)
        return output_video_path

    # Download sticker image
    cache_dir = DUB_STUDIO_DIR / "sticker_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    sticker_id = str(
        sticker_options.get("sticker_id")
        or sticker_options.get("stickerId")
        or "unknown"
    )
    sticker_type = int(sticker_options.get("sticker_type", 1))
    ext = "gif" if sticker_type == 2 else "png"
    cached_path = cache_dir / f"{sticker_id}.{ext}"

    if not cached_path.exists():
        try:
            run(
                ["ffmpeg", "-y", "-i", image_url, str(cached_path)],
                cwd=ROOT,
                timeout=30.0,
            )
            logger.info(f"Downloaded sticker to {cached_path}")
        except Exception as exc:
            logger.error(f"Failed to download sticker image: {exc}")
            import shutil
            shutil.copy2(input_video_path, output_video_path)
            return output_video_path

    if not cached_path.exists():
        import shutil
        shutil.copy2(input_video_path, output_video_path)
        return output_video_path

    # Get video dimensions
    video_meta = get_video_meta(input_video_path)
    width = int(video_meta.get("width", 1920))
    height = int(video_meta.get("height", 1080))

    # Get sticker dimensions
    sticker_meta = get_video_meta(cached_path) if ext == "gif" else {}
    if sticker_meta:
        sw = int(sticker_meta.get("width", width // 4))
        sh = int(sticker_meta.get("height", height // 4))
    else:
        sw, sh = width // 4, height // 4

    # Scale sticker
    sw_scaled = int(sw * scale)
    sh_scaled = int(sh * scale)
    sw_scaled = max(1, sw_scaled)
    sh_scaled = max(1, sh_scaled)

    # Calculate position (ffmpeg overlay uses top-left origin)
    # transform_x: -1 = left edge, 0 = center, 1 = right edge
    # transform_y: -1 = top, 0 = center, 1 = bottom (but we want upper area)
    overlay_x = int((width - sw_scaled) * ((transform_x + 1) / 2))
    overlay_y = int((height - sh_scaled) * ((transform_y + 1) / 2))
    overlay_x = max(0, overlay_x)
    overlay_y = max(0, overlay_y)

    logger.info(
        f"Applying sticker overlay: size={sw_scaled}x{sh_scaled}, pos=({overlay_x},{overlay_y}), "
        f"sticker_id={sticker_id}, type={'GIF' if ext == 'gif' else 'PNG'}"
    )

    # Build ffmpeg command
    if ext == "gif":
        # For GIF stickers, loop forever and scale to desired size
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_video_path),
            "-ignore_loop", "1",
            "-i", str(cached_path),
            "-filter_complex",
            f"[1:v]scale={sw_scaled}:{sh_scaled}:force_original_aspect_ratio=decrease,"
            f"pad={sw_scaled}:{sh_scaled}:(ow-iw)/2:(oh-ih)/2:color=0x00000000@0"
            f"[sticker];[0:v][sticker]overlay={overlay_x}:{overlay_y}:format=auto",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_video_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_video_path),
            "-i", str(cached_path),
            "-filter_complex",
            f"[1:v]scale={sw_scaled}:{sh_scaled}:force_original_aspect_ratio=decrease,"
            f"pad={sw_scaled}:{sh_scaled}:(ow-iw)/2:(oh-ih)/2:color=0x00000000@0"
            f"[sticker];[0:v][sticker]overlay={overlay_x}:{overlay_y}:format=auto",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_video_path),
        ]

    try:
        run(cmd, cwd=ROOT)
    except Exception as exc:
        logger.error(f"Sticker overlay ffmpeg failed: {exc}")
        import shutil
        shutil.copy2(input_video_path, output_video_path)

    return output_video_path


def hex_to_rgb_float(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        return (1.0, 1.0, 1.0)
    return tuple(int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4))


def bottom_offset_to_transform_y(height: int, bottom_offset: int) -> float:
    safe_height = max(height, 1)
    normalized_from_bottom = bottom_offset / safe_height
    return max(-0.94, min(-0.62, -0.92 + normalized_from_bottom * 1.25))


def subtitle_region_to_transform_y(
    video_meta: dict[str, Any],
    subtitle_region: dict[str, Any],
    subtitle_preset: dict[str, Any],
) -> float:
    effective_region = resolve_subtitle_region_for_position(video_meta, subtitle_region, subtitle_preset)
    safe_height = max(int(video_meta.get("height") or 1), 1)
    center_y = int(effective_region.get("y", 0)) + int(effective_region.get("h", 0)) / 2
    normalized = center_y / safe_height
    return max(-0.82, min(0.82, (0.5 - normalized) * 1.72))


def create_capcut_draft(
    *,
    draft_root: str,
    video_path: Path,
    dub_audio_path: Path,
    subtitles: list[SubtitleLine],
    subtitle_preset: dict[str, Any],
    subtitle_region: dict[str, Any],
    video_meta: dict[str, Any],
    analysis_name: str,
    flattened_video_path: Path | None = None,
    sticker_options: dict[str, Any] | None = None,
    ) -> str:
    from src.pyJianYingDraft import (
        AudioMaterial,
        AudioSegment as DraftAudioSegment,
        ClipSettings,
        DraftFolder,
        StickerSegment,
        TextBackground,
        TextBorder,
        TextSegment,
        TextShadow,
        TextStyle,
        Timerange,
        TrackType,
        VideoMaterial,
        VideoSegment,
        trange,
    )
    from src.pyJianYingDraft.metadata import FontType

    if not draft_root:
        raise RuntimeError("Draft root is empty. Configure a CapCut draft directory before exporting draft output.")
    draft_folder = DraftFolder(draft_root)
    draft_name = f"{Path(analysis_name).stem}_dubstudio_{time.strftime('%Y%m%d_%H%M%S')}"
    subtitle_enabled = bool(subtitle_preset.get("enabled", True))
    use_flattened_video = flattened_video_path is not None and not subtitle_enabled
    meta_for_draft = get_video_meta(flattened_video_path) if use_flattened_video else video_meta
    fps = max(24, int(round(float(meta_for_draft.get("fps") or 30))))
    script = draft_folder.create_draft(
        draft_name=draft_name,
        width=int(meta_for_draft["width"]),
        height=int(meta_for_draft["height"]),
        fps=fps,
        allow_replace=True,
    )
    if use_flattened_video:
        script.add_track(TrackType.video, "final_video", relative_index=0)
        script.add_track(TrackType.audio, "final_audio", relative_index=10)
        duration_us = int(meta_for_draft["durationMs"]) * 1000
        video_material = VideoMaterial(str(flattened_video_path))
        video_segment = VideoSegment(
            material=video_material,
            target_timerange=Timerange(0, duration_us),
            source_timerange=Timerange(0, min(duration_us, video_material.duration)),
            volume=0.0,
        )
        script.add_segment(video_segment, "final_video")
        audio_material = AudioMaterial(str(dub_audio_path))
        audio_segment = DraftAudioSegment(
            material=audio_material,
            target_timerange=Timerange(0, min(duration_us, audio_material.duration)),
            source_timerange=Timerange(0, min(duration_us, audio_material.duration)),
            volume=1.0,
        )
        script.add_segment(audio_segment, "final_audio")
        script.save()
        return str(Path(draft_root) / draft_name)

    script.add_track(TrackType.video, "main_track", relative_index=0)
    script.add_track(TrackType.audio, "dub_audio", relative_index=10)
    if subtitle_enabled:
        script.add_track(TrackType.text, "vietsub_track", relative_index=20)

    duration_us = int(video_meta["durationMs"]) * 1000
    video_material = VideoMaterial(str(video_path))
    video_segment = VideoSegment(
        material=video_material,
        target_timerange=Timerange(0, duration_us),
        source_timerange=Timerange(0, min(duration_us, video_material.duration)),
        volume=0.0,
    )
    script.add_segment(video_segment, "main_track")

    audio_material = AudioMaterial(str(dub_audio_path))
    audio_segment = DraftAudioSegment(
        material=audio_material,
        target_timerange=Timerange(0, min(duration_us, audio_material.duration)),
        source_timerange=Timerange(0, min(duration_us, audio_material.duration)),
        volume=1.0,
    )
    script.add_segment(audio_segment, "dub_audio")

    clip_settings = ClipSettings(
        transform_x=0.0,
        transform_y=subtitle_region_to_transform_y(video_meta, subtitle_region, subtitle_preset),
    )
    style = TextStyle(
        size=max(float(subtitle_preset.get("fontSize", 18)) * 0.52, 7.5),
        color=hex_to_rgb_float(subtitle_preset.get("fontColor", "#ffd200")),
        alpha=1.0,
        align=1,
        auto_wrapping=True,
        max_line_width=0.82,
    )
    border = TextBorder(alpha=1.0, color=hex_to_rgb_float(subtitle_preset.get("strokeColor", "#000000")), width=min(max(float(subtitle_preset.get("strokeWidth", 2)) * 18, 26.0), 64.0))
    shadow = TextShadow(alpha=0.9, color=(0.0, 0.0, 0.0), diffuse=12.0, distance=3.0, angle=-90.0)
    background = None
    if bool(subtitle_preset.get("boxEnabled", False)):
        background = TextBackground(
            color=str(subtitle_preset.get("boxFillColor", "#77b8ee")),
            style=2 if str(subtitle_preset.get("boxLayoutMode", "line")).strip().lower() == "unified" else 1,
            alpha=max(0.0, min(float(subtitle_preset.get("boxFillOpacity", 0.86)), 1.0)),
            round_radius=max(0.0, min(float(subtitle_preset.get("boxRadius", 16)) / 48.0, 1.0)),
            height=max(0.12, min(0.24, 0.12 + float(subtitle_preset.get("boxPaddingY", 12)) / 140.0)),
            width=max(0.14, min(0.38, 0.14 + float(subtitle_preset.get("boxPaddingX", 24)) / 160.0)),
        )
    draft_font = getattr(FontType, str(subtitle_preset.get("draftFontKey") or "").strip(), None)
    selected_text_effect = str(subtitle_preset.get("textEffect") or "").strip()
    if subtitle_enabled:
        for item in subtitles:
            timerange = Timerange(int(item.start_ms) * 1000, max(int(item.end_ms - item.start_ms), 120) * 1000)
            text_segment = TextSegment(
                text=item.content,
                timerange=timerange,
                font=draft_font,
                style=style,
                clip_settings=clip_settings,
                border=border,
                background=background,
                shadow=shadow,
            )
            if selected_text_effect and selected_text_effect != "none":
                text_segment.add_effect(selected_text_effect)
            script.add_segment(text_segment, "vietsub_track")

    sticker_id = (sticker_options or {}).get("stickerId", "")
    if sticker_id:
        sticker_scale = max(0.1, min(float((sticker_options or {}).get("scale", 1.0)), 5.0))
        sticker_transform_x = max(
            -1.0, min(float((sticker_options or {}).get("transform_x", 0.0)), 1.0)
        )
        sticker_transform_y = max(
            -1.0, min(float((sticker_options or {}).get("transform_y", -0.3)), 1.0)
        )
        sticker_track_name = "sticker_track"
        script.add_track(TrackType.sticker, sticker_track_name, relative_index=30)
        video_duration_us = int(video_meta.get("durationMs", 0) or 0) * 1000
        if video_duration_us <= 0:
            video_duration_us = 3_000_000
        clip_settings = ClipSettings(
            scale_x=sticker_scale,
            scale_y=sticker_scale,
            transform_x=sticker_transform_x,
            transform_y=sticker_transform_y,
        )
        sticker_seg = StickerSegment(
            resource_id=sticker_id,
            target_timerange=trange(0, video_duration_us),
            clip_settings=clip_settings,
        )
        script.add_segment(sticker_seg, sticker_track_name)

    script.save()
    return str(Path(draft_root) / draft_name)


def build_default_render_options(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "outputTargets": {"mp4": True, "draft": False},
        "videoCodecMode": "gpu_preferred",
        "targetLanguage": analysis.get("targetLanguage", "vi"),
        "subtitlePreset": {
            "enabled": True,
            "positionPreset": "bottom",
            "fontSize": 14,
            "fontFamily": "arial-bold",
            "fontFamilyLabel": "Arial Bold",
            "fontFamilyName": "Arial",
            "cssFontFamily": "\"Arial Black\", Arial, sans-serif",
            "assFontName": "Arial",
            "draftFontKey": "Poppins_Bold",
            "fontColor": "#ffd200",
            "strokeColor": "#000000",
            "strokeWidth": 2,
            "boxEnabled": False,
            "boxStylePreset": "custom",
            "textEffect": "none",
            "boxLayoutMode": "line",
            "boxFillColor": "#77b8ee",
            "boxFillOpacity": 0.86,
            "boxBorderColor": "#3b82f6",
            "boxBorderOpacity": 1.0,
            "boxBorderWidth": 2,
            "boxRadius": 16,
            "boxPaddingX": 24,
            "boxPaddingY": 12,
            "bottomOffset": 54,
            "cleanupBlurStrength": 14,
            "maxWordsPerChunk": 5,
            "maxCharsPerChunk": 22,
            "punctuationAwareSplit": True,
            "assPrimaryColor": "&H0038D8FF",
            "assOutlineColor": "&H00000000",
        },
        "subtitlePosition": {"bottomOffset": 36},
        "sourceSubtitleCleanupMode": normalize_source_subtitle_cleanup_mode(
            analysis.get("subtitleRegion", {}).get("cleanupMode", "localized_blur")
        ),
        "voiceMapping": {speaker["speakerId"]: speaker["voicePreset"] for speaker in analysis.get("speakers", [])},
        "speakerDetectionMode": "auto",
        "timingMode": "balanced_natural",
        "audioMixMode": "preserve_background",
        "keepOriginalAudio": False,
        "backgroundMusic": {
            "enabled": False,
            "path": "",
            "volume": 0.12,
        },
        "draftRoot": "",
        "outputDirectory": "",
        "introHook": {
            "enabled": True,
            "clipDurationMs": 15000,
            "voice": DEFAULT_VOICES[0],
            "voicePresetKey": DEFAULT_VOICES[0],
            "voiceRateDeltaPercent": 0,
            "useBackgroundAudio": False,
            "backgroundVolume": 0.08,
        },
    }


ANALYSIS_CACHE_VERSION = 3


def analysis_cache_key(input_path: Path) -> str:
    resolved_input = input_path.resolve()
    stat = resolved_input.stat()
    source_files = [
        Path(__file__).resolve(),
        Path(inspect.getsourcefile(analyze_with_whisperx) or "").resolve(),
        Path(inspect.getsourcefile(analyze_with_local_whisper) or "").resolve(),
    ]
    source_signature = {
        str(path): path.stat().st_mtime_ns
        for path in source_files
        if str(path) and path.exists()
    }
    payload = {
        "cacheVersion": ANALYSIS_CACHE_VERSION,
        "inputPath": str(resolved_input),
        "inputSize": int(stat.st_size),
        "inputMtimeNs": int(stat.st_mtime_ns),
        "transcribeProvider": DUB_TRANSCRIBE_PROVIDER or "auto",
        "translateProvider": DUB_TRANSLATE_PROVIDER,
        "whisperxModel": WHISPERX_MODEL,
        "whisperxDiarizationModel": WHISPERX_DIARIZATION_MODEL,
        "whisperxDiarizationMaxSpeakers": WHISPERX_DIARIZATION_MAX_SPEAKERS,
        "useGpu": bool(DUB_USE_GPU),
        "sourceSignature": source_signature,
    }
    return hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def analysis_cache_dir(cache_key: str) -> Path:
    return ensure_dir(DUB_STUDIO_DIR / "_analysis_cache" / cache_key)


def restore_cached_analysis(
    *,
    cache_key: str,
    job_id: str,
    input_path: Path,
    dirs: dict[str, Path],
    target_language: str,
) -> dict[str, Any] | None:
    cache_dir = analysis_cache_dir(cache_key)
    cache_json = cache_dir / "analysis.json"
    if not cache_json.exists():
        return None

    try:
        cached_analysis = read_json(cache_json)
    except Exception:
        return None

    restored = copy.deepcopy(cached_analysis)
    thumbnail_cache = cache_dir / "thumbnail.jpg"
    target_thumbnail = dirs["analysis"] / "thumbnail.jpg"
    if thumbnail_cache.exists():
        shutil.copy2(thumbnail_cache, target_thumbnail)

    target_speaker_dir = ensure_dir(dirs["analysis"] / "speakers")
    cached_speaker_dir = cache_dir / "speakers"
    if cached_speaker_dir.exists():
        for candidate in cached_speaker_dir.glob("*_sample.wav"):
            shutil.copy2(candidate, target_speaker_dir / candidate.name)

    restored["jobId"] = job_id
    restored["inputPath"] = str(input_path.resolve())
    restored["analysisDir"] = str(dirs["analysis"])
    restored["thumbnailPath"] = str(
        target_thumbnail if target_thumbnail.exists() else thumbnail_cache
    )
    restored["targetLanguage"] = (
        target_language or restored.get("targetLanguage") or "vi"
    )
    restored["renderDefaults"] = {
        **(restored.get("renderDefaults") or {}),
        "targetLanguage": restored["targetLanguage"],
    }
    warnings = list(restored.get("warnings") or [])
    warnings.append("Kết quả phân tích được khôi phục từ cache để tăng tốc re-analyze.")
    restored["warnings"] = list(dict.fromkeys(warnings))

    for speaker in restored.get("speakers") or []:
        speaker_id = str(speaker.get("speakerId") or "speaker_1")
        sample_path = target_speaker_dir / f"{speaker_id}_sample.wav"
        speaker["samplePath"] = str(sample_path) if sample_path.exists() else ""
        speaker["voiceCloneReady"] = sample_path.exists()
    return restored


def persist_analysis_cache(*, cache_key: str, analysis: dict[str, Any]) -> None:
    cache_dir = analysis_cache_dir(cache_key)
    write_json(cache_dir / "analysis.json", analysis)

    thumbnail_path = Path(str(analysis.get("thumbnailPath") or "")).expanduser()
    if thumbnail_path.exists():
        shutil.copy2(thumbnail_path, cache_dir / "thumbnail.jpg")

    analysis_dir = Path(str(analysis.get("analysisDir") or "")).expanduser()
    speaker_dir = analysis_dir / "speakers"
    cache_speaker_dir = ensure_dir(cache_dir / "speakers")
    if speaker_dir.exists():
        for candidate in speaker_dir.glob("*_sample.wav"):
            shutil.copy2(candidate, cache_speaker_dir / candidate.name)


def do_analyze(
    job_id: str,
    input_path: Path,
    output_json: Path,
    *,
    target_language: str = "vi",
) -> dict[str, Any]:
    if whisperx_disabled():
        return do_analyze_resilient(job_id, input_path, output_json)
    dirs = ensure_job_dirs(job_id)
    video_meta = get_video_meta(input_path)
    thumbnail_path = dirs["analysis"] / "thumbnail.jpg"
    raw_srt_path = dirs["analysis"] / "transcript_raw.srt"
    merged_srt_path = dirs["analysis"] / "transcript_merged.srt"
    whisperx_audio_path = dirs["analysis"] / "transcript_whisperx.wav"

    emit_progress(phase="analysis", step="prepare", progress=0.05, message="Đang đọc thông tin video")
    extract_thumbnail(input_path, thumbnail_path)
    emit_progress(phase="analysis", step="transcribe", progress=0.24, message=f"Đang nhận diện lời nói bằng WhisperX {WHISPERX_MODEL}")
    whisperx_analysis = analyze_with_whisperx(
        video_path=input_path,
        audio_path=whisperx_audio_path,
        raw_srt_path=raw_srt_path,
        merged_srt_path=merged_srt_path,
        language=None,
    )
    
    sample_paths: dict[str, Path] = {}

    raw_subtitles = whisperx_analysis["rawSubtitles"]
    if not raw_subtitles:
        raise RuntimeError("No speech segments were detected from the input video.")
    transcript_text = " ".join(item.content for item in raw_subtitles[:24])
    detected_language = whisperx_analysis.get("sourceLanguage") or ""
    heuristic_language, heuristic_confidence, alternatives = detect_source_language(transcript_text)
    source_language = detected_language if detected_language in LANGUAGE_OPTIONS else heuristic_language
    language_confidence = 0.92 if detected_language == heuristic_language else max(0.74, heuristic_confidence)
    emit_progress(phase="analysis", step="language", progress=0.52, message="Đang xác nhận ngôn ngữ nguồn")
    speaker_count = max(int(whisperx_analysis.get("speakerCount", 1)), 1)
    speaker_confidence = float(whisperx_analysis.get("speakerConfidence", 0.42))
    voice_layout = str(whisperx_analysis.get("voiceLayout") or "single_voice")
    speaker_stats = whisperx_analysis.get("speakerStats") or {}
    main_speaker_id = whisperx_analysis.get("mainSpeakerId") or "speaker_1"
    segments = []
    for index, item in enumerate(whisperx_analysis.get("mergedSegments") or [], start=1):
        subtitle_text = normalize_text(item.get("text") or "")
        if not subtitle_text:
            continue
        speaker_id = item.get("speakerId") or "speaker_1"
        segments.append(
            {
                "id": f"seg_{index:04d}",
                "index": index,
                "startMs": int(item["startMs"]),
                "endMs": int(item["endMs"]),
                "speakerId": speaker_id,
                "sourceText": subtitle_text,
                "translatedText": "",
                "delivery": "neutral",
                "subtitleChunks": split_display_text(subtitle_text),
            }
        )

    refinement = {}

    if segments:
        emit_progress(phase="analysis", step="samples", progress=0.68, message="Đang tách mẫu giọng từng nhân vật")
        sample_paths = extract_speaker_samples(input_path, segments, dirs["analysis"] / "speakers")

    speakers = build_speakers(
        speaker_count,
        speaker_stats=speaker_stats,
        main_speaker_id=main_speaker_id,
        refinement=refinement,
        sample_paths=sample_paths,
    )
    emit_progress(phase="analysis", step="speaker", progress=0.7, message="Đang gom nhóm người nói theo WhisperX")

    subtitle_region = default_subtitle_region(video_meta)
    warnings: list[str] = list(whisperx_analysis.get("warnings") or [])
    if language_confidence < 0.58:
        warnings.append("Độ tự tin ngôn ngữ nguồn đang thấp. Nên kiểm tra và sửa tay trước khi render.")
    if voice_layout == "single_voice":
        warnings.append("Audio goc hien tai giong mot giọng chung. He thong se uu tien dung mot giọng de tranh nham nhan vat.")
    elif speaker_confidence < 0.52:
        warnings.append("Số speaker được ước lượng theo heuristic. Nếu video là hội thoại, nên kiểm tra lại mapping giọng.")

    translated_cache_path = dirs["analysis"] / "translated.json"
    emit_progress(
        phase="analyze",
        step="translate",
        progress=0.81,
        message=f"Đang dịch subtitle sang {target_language.upper()}",
    )
    segments = translate_segments(
        segments,
        source_language,
        translated_cache_path,
        target_language=target_language,
        phase="analyze",
    )
    subtitle_timeline = build_subtitle_timeline(segments)

    analysis = {
        "jobId": job_id,
        "inputPath": str(input_path),
        "thumbnailPath": str(thumbnail_path),
        "analysisDir": str(dirs["analysis"]),
        "videoMeta": video_meta,
        "sourceLanguage": source_language,
        "targetLanguage": target_language,
        "languageConfidence": language_confidence,
        "languageAlternatives": alternatives,
        "speakers": speakers,
        "speakerConfidence": speaker_confidence,
        "mainSpeakerId": main_speaker_id,
        "detectedSpeakerCountRaw": speaker_count,
        "voiceLayout": voice_layout,
        "segments": segments,
        "transcriptionProvider": f"whisperx:{WHISPERX_MODEL}",
        "alignmentProvider": "whisperx",
        "diarizationProvider": "whisperx" if not any("fallback heuristic speaker" in item for item in warnings) else "heuristic_fallback",
        "subtitleRegion": subtitle_region,
        "subtitleTimeline": subtitle_timeline,
        "subtitleSrt": compose_srt_from_timeline(subtitle_timeline),
        "subtitleTimelineSource": "ai_generated",
        "warnings": warnings,
        "renderDefaults": build_default_render_options(
            {
                "speakers": speakers,
                "subtitleRegion": subtitle_region,
                "voiceLayout": voice_layout,
                "targetLanguage": target_language,
            }
        ),
    }
    write_json(output_json, analysis)
    emit_progress(phase="analysis", step="done", progress=1.0, message="Phân tích xong", status="success")
    emit("RESULT", {"analysisPath": str(output_json), "thumbnailPath": str(thumbnail_path)})
    return analysis


def do_analyze_resilient(
    job_id: str,
    input_path: Path,
    output_json: Path,
    *,
    target_language: str = "vi",
) -> dict[str, Any]:
    emit_progress(
        phase="analyze",
        step="prepare",
        progress=0.01,
        message="Đang chuẩn bị phân tích nhanh...",
    )
    dirs = ensure_job_dirs(job_id)
    cache_key = analysis_cache_key(input_path)
    emit_progress(
        phase="analyze",
        step="cache",
        progress=0.02,
        message="Đang kiểm tra cache phân tích theo file video...",
    )
    cached_analysis = restore_cached_analysis(
        cache_key=cache_key,
        job_id=job_id,
        input_path=input_path,
        dirs=dirs,
        target_language=target_language,
    )
    if cached_analysis is not None:
        write_json(output_json, cached_analysis)
        emit_progress(
            phase="analyze",
            step="done",
            progress=1.0,
            message="Phân tích xong (cache hit)",
            status="success",
        )
        emit(
            "RESULT",
            {
                "analysisPath": str(output_json),
                "thumbnailPath": str(cached_analysis.get("thumbnailPath") or ""),
            },
        )
        return cached_analysis
    video_meta = get_video_meta(input_path)
    thumbnail_path = dirs["analysis"] / "thumbnail.jpg"
    raw_srt_path = dirs["analysis"] / "transcript_raw.srt"
    merged_srt_path = dirs["analysis"] / "transcript_merged.srt"
    whisperx_audio_path = dirs["analysis"] / "transcript_whisperx.wav"

    emit_progress(phase="analyze", step="metadata", progress=0.05, message="Đang đọc thông tin video")
    extract_thumbnail(input_path, thumbnail_path)

    transcribe_provider = DUB_TRANSCRIBE_PROVIDER or "auto"
    transcription_provider = f"whisperx:{WHISPERX_MODEL}"
    alignment_provider = "whisperx"
    diarization_provider = "whisperx"
    sample_paths: dict[str, Path] = {}

    use_local_transcriber = transcribe_provider in LOCAL_TRANSCRIBE_PROVIDERS
    if use_local_transcriber:
        emit_progress(phase="analyze", step="transcribe", progress=0.24, message="Đang nhận diện lời nói bằng ffmpeg-whisper local")
        transcription = analyze_with_local_whisper(
            video_path=input_path,
            raw_srt_path=raw_srt_path,
            merged_srt_path=merged_srt_path,
            language=None,
            explicit_local_mode=True,
        )
        transcription_provider = "ffmpeg-whisper:local"
        alignment_provider = "none"
        diarization_provider = "heuristic_fallback"
    else:
        emit_progress(phase="analyze", step="transcribe", progress=0.15, message=f"Đang nhận diện lời nói bằng WhisperX {WHISPERX_MODEL}")
        try:
            transcription = analyze_with_whisperx(
                video_path=input_path,
                audio_path=whisperx_audio_path,
                raw_srt_path=raw_srt_path,
                merged_srt_path=merged_srt_path,
                language=None,
            )
            
            if any("fallback heuristic speaker" in item for item in transcription.get("warnings") or []):
                diarization_provider = "heuristic_fallback"
        except Exception as exc:
            fallback_reason = normalize_text(str(exc)) or exc.__class__.__name__
            emit_progress(
                phase="analyze",
                step="transcribe_fallback",
                progress=0.3,
                message="WhisperX lỗi, chuyển sang ffmpeg-whisper offline",
            )
            transcription = analyze_with_local_whisper(
                video_path=input_path,
                raw_srt_path=raw_srt_path,
                merged_srt_path=merged_srt_path,
                language=None,
                fallback_reason=fallback_reason,
            )
            transcription_provider = "ffmpeg-whisper:local"
            alignment_provider = "none"
            diarization_provider = "heuristic_fallback"
            sample_paths = {}

    raw_subtitles = transcription["rawSubtitles"]
    if not raw_subtitles:
        raise RuntimeError("No speech segments were detected from the input video.")
    transcript_text = " ".join(item.content for item in raw_subtitles[:24])
    detected_language = transcription.get("sourceLanguage") or ""
    heuristic_language, heuristic_confidence, alternatives = detect_source_language(transcript_text)
    source_language = detected_language if detected_language in LANGUAGE_OPTIONS else heuristic_language
    language_confidence = 0.92 if detected_language == heuristic_language else max(0.74, heuristic_confidence)
    emit_progress(phase="analyze", step="language", progress=0.55, message="Đang xác nhận ngôn ngữ nguồn")

    speaker_count = max(int(transcription.get("speakerCount", 1)), 1)
    speaker_confidence = float(transcription.get("speakerConfidence", 0.42))
    speaker_stats = transcription.get("speakerStats") or {}
    main_speaker_id = transcription.get("mainSpeakerId") or "speaker_1"
    voice_layout = str(transcription.get("voiceLayout") or "single_voice")

    segments = []
    for index, item in enumerate(transcription.get("mergedSegments") or [], start=1):
        subtitle_text = normalize_text(item.get("text") or "")
        if not subtitle_text:
            continue
        segments.append(
            {
                "id": f"seg_{index:04d}",
                "index": index,
                "startMs": int(item["startMs"]),
                "endMs": int(item["endMs"]),
                "speakerId": item.get("speakerId") or "speaker_1",
                "sourceText": subtitle_text,
                "translatedText": "",
                "delivery": "neutral",
                "subtitleChunks": split_display_text(subtitle_text),
            }
        )
    refinement = {}

    if segments:
        emit_progress(phase="analyze", step="diarize", progress=0.69, message="Đang tách mẫu giọng từng nhân vật")
        sample_paths = extract_speaker_samples(input_path, segments, dirs["analysis"] / "speakers")

    speakers = build_speakers(
        speaker_count,
        speaker_stats=speaker_stats,
        main_speaker_id=main_speaker_id,
        refinement=refinement,
        sample_paths=sample_paths,
    )
    emit_progress(phase="analyze", step="cluster", progress=0.75, message="Đang gom nhóm người nói")

    subtitle_region = default_subtitle_region(video_meta)
    warnings: list[str] = list(transcription.get("warnings") or [])
    if language_confidence < 0.58:
        warnings.append("Độ tự tin ngôn ngữ nguồn đang thấp. Nên kiểm tra và sửa tay trước khi render.")
    if voice_layout == "single_voice":
        warnings.append("Audio gốc hiện tại giống một giọng chung. Hệ thống sẽ ưu tiên dùng một giọng để tránh nhầm nhân vật.")
    elif speaker_confidence < 0.52:
        warnings.append("Số speaker được ước lượng theo heuristic. Nếu video là hội thoại, nên kiểm tra lại mapping giọng.")

    translated_cache_path = dirs["analysis"] / "translated.json"
    emit_progress(
        phase="analyze",
        step="translate",
        progress=0.81,
        message=f"Đang dịch subtitle sang {target_language.upper()}",
    )
    segments = translate_segments(
        segments,
        source_language,
        translated_cache_path,
        target_language=target_language,
        phase="analyze",
    )
    subtitle_timeline = build_subtitle_timeline(segments)

    analysis = {
        "jobId": job_id,
        "inputPath": str(input_path),
        "thumbnailPath": str(thumbnail_path),
        "analysisDir": str(dirs["analysis"]),
        "videoMeta": video_meta,
        "sourceLanguage": source_language,
        "targetLanguage": target_language,
        "languageConfidence": language_confidence,
        "languageAlternatives": alternatives,
        "speakers": speakers,
        "speakerConfidence": speaker_confidence,
        "mainSpeakerId": main_speaker_id,
        "detectedSpeakerCountRaw": speaker_count,
        "voiceLayout": voice_layout,
        "segments": segments,
        "transcriptionProvider": transcription_provider,
        "alignmentProvider": alignment_provider,
        "diarizationProvider": diarization_provider,
        "subtitleRegion": subtitle_region,
        "subtitleTimeline": subtitle_timeline,
        "subtitleSrt": compose_srt_from_timeline(subtitle_timeline),
        "subtitleTimelineSource": "ai_generated",
        "warnings": warnings,
        "renderDefaults": build_default_render_options(
            {
                "speakers": speakers,
                "subtitleRegion": subtitle_region,
                "voiceLayout": voice_layout,
                "targetLanguage": target_language,
            }
        ),
    }
    persist_analysis_cache(cache_key=cache_key, analysis=analysis)
    write_json(output_json, analysis)
    emit_progress(phase="analyze", step="done", progress=1.0, message="Phân tích xong", status="success")
    emit("RESULT", {"analysisPath": str(output_json), "thumbnailPath": str(thumbnail_path)})
    return analysis


def do_render(analysis_path: Path, render_options_path: Path, output_json: Path) -> dict[str, Any]:
    emit_progress(
        phase="render",
        step="prepare",
        progress=0.01,
        message="Đang kiểm tra thư viện và model cho render...",
    )
    prepare_runtime("render")
    analysis = read_json(analysis_path)
    render_options = read_json(render_options_path) if render_options_path.exists() else {}
    dirs = ensure_job_dirs(analysis["jobId"])
    input_path = Path(analysis["inputPath"]).resolve()
    subtitle_preset = {**analysis.get("renderDefaults", {}).get("subtitlePreset", {}), **render_options.get("subtitlePreset", {})}
    subtitle_preset["watermarkOptions"] = {
        "enabled": bool(render_options.get("watermarkEnabled", False)),
        "path": render_options.get("watermarkPath", ""),
        "position": render_options.get("watermarkPosition", "top-right"),
        "scale": float(render_options.get("watermarkScale", 0.15)),
    }
    voice_mapping = {**analysis.get("renderDefaults", {}).get("voiceMapping", {}), **render_options.get("voiceMapping", {})}
    uses_vieneu_voice = any(
        is_vieneu_voice_preset(resolve_voice_preset(voice))
        for voice in voice_mapping.values()
    )
    uses_valtec_voice = any(
        is_valtec_voice_preset(resolve_voice_preset(voice))
        for voice in voice_mapping.values()
    )
    requested_cleanup_mode = render_options.get("sourceSubtitleCleanupMode")
    if requested_cleanup_mode is None:
        requested_cleanup_mode = analysis.get("subtitleRegion", {}).get("cleanupMode", "localized_blur")
    draft_root = render_options.get("draftRoot") or analysis.get("renderDefaults", {}).get("draftRoot") or getattr(config, "DRAFT_DIR", "")
    output_directory = render_options.get("outputDirectory") or ""
    keep_original_audio = bool(render_options.get("keepOriginalAudio", False))
    audio_mix_mode = normalize_audio_mix_mode(
        render_options.get("audioMixMode") or analysis.get("renderDefaults", {}).get("audioMixMode"),
        keep_original_audio=keep_original_audio,
    )
    timing_mode = render_options.get("timingMode", "balanced_natural")
    video_codec_mode = str(
        render_options.get("videoCodecMode")
        or analysis.get("renderDefaults", {}).get("videoCodecMode")
        or "gpu_preferred"
    )
    source_language = render_options.get("sourceLanguage") or analysis.get("sourceLanguage") or "zh"
    target_language = render_options.get("targetLanguage") or analysis.get("targetLanguage") or "vi"
    output_targets = render_options.get("outputTargets") or {"mp4": True, "draft": False}
    output_ratio = render_options.get("outputRatio") or "9:16"
    subtitle_enabled = bool(subtitle_preset.get("enabled", True))
    effective_subtitle_region = resolve_subtitle_region_for_position(
        analysis["videoMeta"],
        analysis.get("subtitleRegion", {}),
        subtitle_preset,
    )
    intro_hook = {
        **analysis.get("renderDefaults", {}).get("introHook", {}),
        **render_options.get("introHook", {}),
    }
    background_music = {
        **analysis.get("renderDefaults", {}).get("backgroundMusic", {}),
        **(render_options.get("backgroundMusic") or {}),
    }
    background_music_enabled = bool(background_music.get("enabled", False))
    background_music_path_raw = str(background_music.get("path") or "").strip()
    background_music_path = (
        Path(background_music_path_raw).expanduser().resolve()
        if background_music_enabled and background_music_path_raw
        else None
    )
    if background_music_enabled and (
        background_music_path is None
        or not background_music_path.exists()
        or not background_music_path.is_file()
    ):
        raise RuntimeError("File nhạc nền đã bật nhưng không còn tồn tại. Hãy chọn lại file audio.")
    background_music_volume = max(
        0.0, min(float(background_music.get("volume", 0.12)), 2.0)
    )
    if intro_hook.get("enabled") and is_vieneu_voice_preset(resolve_voice_preset(intro_hook.get("voice") or "")):
        uses_vieneu_voice = True
    if intro_hook.get("enabled") and is_valtec_voice_preset(resolve_voice_preset(intro_hook.get("voice") or "")):
        uses_valtec_voice = True
    if DUB_USE_VIENEU and uses_vieneu_voice:
        ensure_vieneu_runtime(phase="render", step="prepare", progress=0.05)
    if DUB_USE_VALTEC and uses_valtec_voice:
        ensure_valtec_runtime(
            phase="render",
            step="prepare",
            progress=0.055,
            preload_zeroshot=any(
                resolve_voice_preset(voice) == VALTEC_CLONE_PRESET
                or is_valtec_reference_voice(resolve_voice_preset(voice))
                for voice in voice_mapping.values()
            )
            or resolve_voice_preset(intro_hook.get("voice") or "") == VALTEC_CLONE_PRESET
            or is_valtec_reference_voice(resolve_voice_preset(intro_hook.get("voice") or "")),
        )

    emit_progress(phase="render", step="prepare", progress=0.08, message="Đang chuẩn bị dữ liệu render")
    os.environ["CAPCUT_VIDEO_CODEC_MODE"] = video_codec_mode
    safe_print(f"Using video codec mode: {video_codec_mode}", flush=True)
    safe_print(f"Using video codec: {choose_video_codec()[0]}", flush=True)
    translated_cache_path = dirs["analysis"] / "translated.json"
    editable_subtitle_timeline = analysis.get("subtitleTimeline") or []
    segments = copy.deepcopy(analysis["segments"])
    segments = translate_segments(
        segments,
        source_language,
        translated_cache_path,
        target_language=target_language,
        phase="render",
    )
    rebuilt_subtitle_timeline = build_subtitle_timeline(segments)
    timeline_text_by_segment = {
        str(item.get("segmentId") or ""): normalize_text(item.get("text") or "")
        for item in editable_subtitle_timeline
        if str(item.get("segmentId") or "")
    }
    segment_text_by_id = {
        str(segment.get("id") or ""): normalize_text(
            pick_best_localized_text(
                segment.get("translatedText") or "",
                "",
                segment.get("sourceText") or "",
            )
        )
        for segment in segments
        if str(segment.get("id") or "")
    }
    timeline_source = str(analysis.get("subtitleTimelineSource") or "").strip().lower()
    timeline_is_user_edited = timeline_source in {"edited", "imported"}
    missing_segment_mappings = len(timeline_text_by_segment) < len(rebuilt_subtitle_timeline)
    timeline_is_stale = (not timeline_is_user_edited) and (
        missing_segment_mappings
        or any(
            segment_text_by_id.get(segment_id, "") != timeline_text
            for segment_id, timeline_text in timeline_text_by_segment.items()
        )
    )
    subtitle_timeline = (
        rebuilt_subtitle_timeline
        if not editable_subtitle_timeline or timeline_is_stale
        else editable_subtitle_timeline
    )
    segments = apply_subtitle_timeline_to_segments(segments, subtitle_timeline)
    subtitle_timeline = renumber_subtitle_timeline(subtitle_timeline)
    display_subtitles: list[SubtitleLine] = split_subtitle_lines_for_display(
        subtitle_timeline_to_lines(subtitle_timeline),
        max_words=int(subtitle_preset.get("maxWordsPerChunk", 5)),
        max_chars=int(subtitle_preset.get("maxCharsPerChunk", 22)),
        punctuation_aware=bool(subtitle_preset.get("punctuationAwareSplit", True)),
    )
    dynamic_regions: list[dict[str, Any]] = []
    subtitle_positions: list[dict[str, int]] = []
    subtitle_ass_path = dirs["render"] / "vietsub_display.ass"
    subtitle_srt_path = dirs["render"] / "vietsub_display.srt"
    if subtitle_enabled:
        requested_cleanup_normalized = normalize_source_subtitle_cleanup_mode(
            requested_cleanup_mode
        )
        if requested_cleanup_normalized != "none":
            original_subtitles = subtitles_from_analysis_segments(analysis.get("segments") or [])
            dynamic_regions, _ = build_dynamic_subtitle_regions(
                input_path,
                video_meta=analysis["videoMeta"],
                subtitles=original_subtitles,
                fallback_region=effective_subtitle_region,
            )
            subtitle_positions = build_stable_subtitle_positions(
                display_subtitles,
                dynamic_regions=dynamic_regions,
                fallback_region=effective_subtitle_region,
                video_meta=analysis["videoMeta"],
            )
            if any(r.get("detected") for r in dynamic_regions):
                dynamic_regions = [r for r in dynamic_regions if r.get("detected")]
            else:
                # Không phát hiện thấy sub cũ nào trong toàn bộ video -> Không che
                dynamic_regions = []
        
        cleanup_mode = resolve_source_subtitle_cleanup_mode(
            requested_cleanup_mode,
            subtitle_region=effective_subtitle_region,
            dynamic_regions=dynamic_regions,
        )
        
        subtitle_positions = build_stable_subtitle_positions(
            display_subtitles,
            dynamic_regions=dynamic_regions,
            fallback_region=effective_subtitle_region,
            video_meta=analysis["videoMeta"],
        )
        
        subtitle_ass_path.write_text(
            compose_ass(
                display_subtitles,
                video_meta=analysis["videoMeta"],
                subtitle_preset=subtitle_preset,
                subtitle_positions=subtitle_positions,
            ),
            encoding="utf-8",
        )
        subtitle_srt_path.write_text(
            compose_srt(display_subtitles), encoding="utf-8"
        )
    else:
        cleanup_mode = resolve_source_subtitle_cleanup_mode(
            requested_cleanup_mode,
            subtitle_region=effective_subtitle_region,
            dynamic_regions=[],
        )

    emit_progress(phase="render", step="tts", progress=0.44, message="Đang tạo lồng tiếng")
    dub_audio_path = dirs["audio"] / "dub_voice.wav"
    manifest = create_dub_audio(
        job_id=str(analysis.get("jobId") or ""),
        video_meta=analysis["videoMeta"],
        source_video_path=input_path,
        segments=segments,
        voices=voice_mapping,
        timing_mode=timing_mode,
        tts_dir=dirs["tts"],
        dub_audio_path=dub_audio_path,
    )
    manifest_path = dirs["audio"] / "dub_manifest.json"
    manifest_path.write_text(json.dumps([asdict(item) for item in manifest], ensure_ascii=False, indent=2), encoding="utf-8")

    background_audio_path, background_warnings = prepare_background_audio_track(
        video_path=input_path,
        video_meta=analysis["videoMeta"],
        work_dir=dirs["audio"],
        audio_mix_mode=audio_mix_mode,
        keep_original_audio=keep_original_audio,
        phase="render",
        progress=0.6,
    )

    emit_progress(phase="render", step="mix", progress=0.62, message="Đang ghép audio")
    mixed_audio_path = dirs["audio"] / "mixed_audio.wav"
    invoke_create_final_audio_compat(
        input_path,
        dub_audio_path,
        mixed_audio_path,
        audio_mix_mode=audio_mix_mode,
        keep_original_audio=keep_original_audio,
        background_audio_path=background_audio_path,
        background_music_path=background_music_path,
        background_music_volume=background_music_volume,
    )

    outputs: dict[str, Any] = {
        "jobId": analysis["jobId"],
        "previewVideoPath": "",
        "outputVideoPath": "",
        "draftPath": "",
        "dubAudioPath": str(dub_audio_path),
        "mixedAudioPath": str(mixed_audio_path),
        "backgroundAudioPath": str(background_audio_path) if background_audio_path else "",
        "backgroundMusicPath": str(background_music_path) if background_music_path else "",
        "subtitlePath": str(subtitle_ass_path) if subtitle_enabled else "",
        "subtitleSrtPath": str(subtitle_srt_path) if subtitle_enabled else "",
        "manifestPath": str(manifest_path),
        "warnings": list(analysis.get("warnings", [])) + background_warnings,
        "introHook": {"enabled": False},
        "outputDirectory": output_directory,
    }

    sticker_options = render_options.get("stickerOptions") or {}
    ending_video = render_options.get("endingVideo") or {}

    flattened_render_path: Path | None = None
    main_render_path: Path | None = None
    if output_targets.get("mp4", True) or output_targets.get("draft", True):
        emit_progress(phase="render", step="video", progress=0.78, message="Đang xuất MP4")
        main_render_path = dirs["render"] / f"{Path(input_path).stem}_dubstudio_main.mp4"
        if subtitle_enabled:
            burn_subtitles(
                video_path=input_path,
                audio_path=mixed_audio_path,
                subtitles_path=subtitle_ass_path,
                output_path=main_render_path,
                cleanup_mode=cleanup_mode,
                subtitle_region=effective_subtitle_region,
                subtitle_preset=subtitle_preset,
                dynamic_regions=dynamic_regions,
                use_ass=True,
                output_ratio=output_ratio,
            )
        else:
            mux_video_with_audio(video_path=input_path, audio_path=mixed_audio_path, output_path=main_render_path, watermark_options=subtitle_preset.get("watermarkOptions"), video_meta=analysis["videoMeta"], output_ratio=output_ratio)

    if intro_hook.get("enabled", False) and main_render_path is not None:
        emit_progress(phase="render", step="intro_hook", progress=0.86, message="Đang tạo intro hook tự động")
        try:
            intro_result = render_intro_hook(
                input_path=input_path,
                video_meta=analysis["videoMeta"],
                segments=segments,
                source_language=source_language,
                voice_mapping=voice_mapping,
                subtitle_region=effective_subtitle_region,
                subtitle_preset=subtitle_preset,
                subtitle_enabled=subtitle_enabled,
                cleanup_mode=cleanup_mode,
                intro_hook=intro_hook,
                timing_mode=timing_mode,
                dirs=dirs,
                background_music_path=background_music_path,
                background_music_volume=background_music_volume,
                dynamic_regions=dynamic_regions,
                output_ratio=output_ratio,
            )
            flattened_render_path = dirs["render"] / f"{Path(input_path).stem}_dubstudio.mp4"
            concat_rendered_videos(Path(intro_result["videoPath"]), main_render_path, flattened_render_path)
            outputs["introHook"] = intro_result
            if output_targets.get("mp4", True):
                outputs["outputVideoPath"] = str(flattened_render_path)
        except Exception as exc:
            warning_message = f"Tao intro hook that bai, giu video chinh: {exc}"
            outputs["warnings"].append(warning_message)
            emit_progress(
                phase="render",
                step="intro_hook",
                progress=0.88,
                message="Intro hook lỗi, tiếp tục xuất video chính",
                extra={"warning": warning_message[:240]},
            )
            if output_targets.get("mp4", True):
                final_output_path = dirs["render"] / f"{Path(input_path).stem}_dubstudio.mp4"
                main_render_path = finalize_main_render_output(main_render_path, final_output_path)
                outputs["outputVideoPath"] = str(main_render_path)
    elif output_targets.get("mp4", True) and main_render_path is not None:
        final_output_path = dirs["render"] / f"{Path(input_path).stem}_dubstudio.mp4"
        main_render_path = finalize_main_render_output(main_render_path, final_output_path)
        outputs["outputVideoPath"] = str(main_render_path)

    if ending_video.get("enabled", False) and ending_video.get("path") and Path(ending_video["path"]).exists():
        emit_progress(phase="render", step="ending_video", progress=0.87, message="Đang ghép ending video")
        current_video_path = outputs.get("outputVideoPath")
        if current_video_path and Path(current_video_path).exists():
            ending_video_path = Path(ending_video["path"])
            ending_output_path = dirs["render"] / f"{Path(input_path).stem}_dubstudio_with_ending.mp4"
            try:
                concat_ending_video_safe(Path(current_video_path), ending_video_path, ending_output_path)
                if ending_output_path.exists():
                    # Xóa file tạm và ghi đè
                    Path(current_video_path).unlink(missing_ok=True)
                    ending_output_path.rename(Path(current_video_path))
            except Exception as exc:
                warning_message = f"Ghép ending video thất bại: {exc}"
                outputs["warnings"].append(warning_message)
                emit_progress(
                    phase="render",
                    step="ending_video",
                    progress=0.88,
                    message="Ghép ending video lỗi, bỏ qua",
                    extra={"warning": warning_message[:240]},
                )

    # Apply sticker overlay to MP4 output
    if output_targets.get("mp4", True) and sticker_options.get("stickerId"):
        emit_progress(phase="render", step="sticker", progress=0.88, message="Đang thêm sticker vào video")
        sticker_video_path = outputs.get("outputVideoPath") or str(main_render_path or "")
        if sticker_video_path and Path(sticker_video_path).exists():
            sticker_tmp = dirs["render"] / f"{Path(input_path).stem}_sticker_tmp.mp4"
            apply_sticker_overlay(
                input_video_path=Path(sticker_video_path),
                output_video_path=sticker_tmp,
                sticker_options=sticker_options,
                scale=sticker_options.get("scale", 1.0),
                transform_x=sticker_options.get("transform_x", 0.0),
                transform_y=sticker_options.get("transform_y", -0.3),
            )
            if sticker_tmp.exists():
                Path(sticker_video_path).unlink(missing_ok=True)
                sticker_tmp.rename(Path(sticker_video_path))
                outputs["outputVideoPath"] = sticker_video_path

    if output_targets.get("draft", True):
        try:
            emit_progress(phase="render", step="draft", progress=0.9, message="Đang tạo draft CapCut")
            outputs["draftPath"] = create_capcut_draft(
                draft_root=draft_root,
                video_path=input_path,
                dub_audio_path=mixed_audio_path,
                subtitles=display_subtitles,
                subtitle_preset=subtitle_preset,
                subtitle_region=effective_subtitle_region,
                video_meta=analysis["videoMeta"],
                analysis_name=Path(input_path).stem,
                flattened_video_path=flattened_render_path,
                sticker_options=render_options.get("stickerOptions"),
            )
        except Exception as exc:
            outputs["warnings"].append(f"Tạo draft CapCut thất bại: {exc}")

    preview_video_path = (
        outputs.get("outputVideoPath")
        or (str(flattened_render_path) if flattened_render_path is not None else "")
        or (str(main_render_path) if main_render_path is not None else "")
    )
    outputs["previewVideoPath"] = preview_video_path or ""

    write_json(output_json, outputs)
    emit_progress(phase="render", step="done", progress=1.0, message="Render hoàn tất", status="success")
    emit("RESULT", outputs)
    return outputs


def do_prepare(target: str) -> dict[str, Any]:
    emit_progress(
        phase="prepare",
        step="prepare",
        progress=0.01,
        message="Đang kiểm tra môi trường runtime...",
    )
    prepare_runtime(target)
    result = {"target": target, "ready": True}
    emit_progress(
        phase="prepare",
        step="done",
        progress=1.0,
        message="Môi trường đã sẵn sàng.",
        status="success",
    )
    emit("RESULT", result)
    return result


def do_preview_voice(
    *,
    voice: str,
    text: str,
    speaker_id: str,
    job_id: str,
    output_json: Path,
) -> dict[str, Any]:
    input_text = normalize_text(text) or "Xin chào, đây là giọng lồng tiếng thử nghiệm của mình. Bạn thấy có tự nhiên không?"
    preview_text = sanitize_for_tts_or_raise(
        input_text,
        speaker_id=speaker_id or "speaker_1",
        allow_generic_fallback=True,
    )
    selected_voice = resolve_voice_preset(voice)
    extension = resolve_tts_output_extension(
        voice=selected_voice,
        speaker_id=speaker_id or "speaker_1",
        job_id=job_id or "",
    )
    preview_dir = ensure_dir(DUB_STUDIO_DIR / "voice_preview")
    reference_audio = resolve_valtec_reference_audio(selected_voice)
    reference_signature = ""
    if reference_audio is not None and reference_audio.exists():
        stat = reference_audio.stat()
        reference_signature = f"|ref={reference_audio.name}:{stat.st_size}:{stat.st_mtime_ns}"
    cache_scope = (
        f"reference:{selected_voice}{reference_signature}"
        if is_valtec_reference_voice(selected_voice)
        else ("shared" if selected_voice != VALTEC_CLONE_PRESET else f"{speaker_id}|{job_id}")
    )
    cache_key = hashlib.sha1(
        f"{selected_voice}|{cache_scope}|{preview_text}".encode("utf-8", errors="ignore")
    ).hexdigest()[:16]
    preview_file_prefix = (
        "reference"
        if is_valtec_reference_voice(selected_voice)
        else ("shared" if selected_voice != VALTEC_CLONE_PRESET else (speaker_id or "speaker_1"))
    )
    output_path = preview_dir / f"{preview_file_prefix}_{cache_key}{extension}"
    result = {
        "voice": selected_voice,
        "speakerId": speaker_id or "speaker_1",
        "outputPath": str(output_path),
        "text": preview_text,
        "inputText": input_text,
        "textRepaired": preview_text != input_text,
    }
    if output_path.exists() and output_path.stat().st_size > 0:
        write_json(output_json, result)
        emit_progress(
            phase="preview",
            step="done",
            progress=1.0,
            message="Đã dùng lại audio nghe thử có sẵn.",
            status="success",
        )
        emit("RESULT", result)
        return result
    if DUB_USE_VALTEC and is_valtec_voice_preset(selected_voice):
        ensure_valtec_runtime(
            phase="preview",
            step="prepare",
            progress=0.12,
            preload_zeroshot=selected_voice == VALTEC_CLONE_PRESET
            or is_valtec_reference_voice(selected_voice),
        )
    emit_progress(
        phase="preview",
        step="tts",
        progress=0.2,
        message="Đang tạo audio nghe thử giọng đọc...",
    )
    synthesize_tts(
        preview_text,
        selected_voice,
        "+0%",
        output_path,
        speaker_id=speaker_id or "speaker_1",
        job_id=job_id or "",
    )
    write_json(output_json, result)
    emit_progress(
        phase="preview",
        step="done",
        progress=1.0,
        message="Đã tạo xong audio nghe thử.",
        status="success",
    )
    emit("RESULT", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze and render Dub Studio jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--job-id", required=True)
    analyze.add_argument("--input", required=True)
    analyze.add_argument("--output-json", required=True)
    analyze.add_argument("--target-language", default="vi")

    render = subparsers.add_parser("render")
    render.add_argument("--analysis-json", required=True)
    render.add_argument("--render-options-json", required=True)
    render.add_argument("--output-json", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument(
        "--target",
        choices=["analysis", "render", "all"],
        default="all",
    )

    preview_voice = subparsers.add_parser("preview-voice")
    preview_voice.add_argument("--voice", required=True)
    preview_voice.add_argument("--text", required=True)
    preview_voice.add_argument("--speaker-id", default="speaker_1")
    preview_voice.add_argument("--job-id", default="")
    preview_voice.add_argument("--output-json", required=True)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dir(DUB_STUDIO_DIR)

    if args.command == "analyze":
        do_analyze_resilient(
            job_id=args.job_id,
            input_path=Path(args.input).resolve(),
            output_json=Path(args.output_json).resolve(),
            target_language=str(getattr(args, "target_language", "vi") or "vi"),
        )
    elif args.command == "render":
        do_render(
            analysis_path=Path(args.analysis_json).resolve(),
            render_options_path=Path(args.render_options_json).resolve(),
            output_json=Path(args.output_json).resolve(),
        )
    elif args.command == "prepare":
        do_prepare(args.target)
    elif args.command == "preview-voice":
        do_preview_voice(
            voice=args.voice,
            text=args.text,
            speaker_id=args.speaker_id,
            job_id=args.job_id,
            output_json=Path(args.output_json).resolve(),
        )
    return 0


if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = int(main())
    except Exception as exc:  # pragma: no cover
        emit("ERROR", {"message": str(exc)})
        exit_code = 1
    finally:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(exit_code)
