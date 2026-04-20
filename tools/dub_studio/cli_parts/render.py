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
    maybe_upgrade_speaker_segmentation_with_llm,
    refine_speakers_with_ollama,
    resolve_tts_output_extension,
    resolve_voice_preset,
    subtitle_region_detected,
)
from .audio import (
    create_dub_audio,
    create_final_audio,
    create_intro_audio,
    extract_video_clip,
    normalize_audio_mix_mode,
    prepare_background_audio_track,
    synthesize_timed_tts_clip,
    synthesize_tts,
)
from .runtime import prepare_runtime, should_use_llama_cpp, should_use_ollama
from .translation import (
    build_intro_hook_text,
    build_intro_hook_text_with_context,
    build_structured_intro_hook_text,
    generate_intro_hook_via_llama_cpp,
    generate_intro_hook_via_ollama,
    select_intro_hook_window,
    translate_segments,
)

def stable_video_codec() -> tuple[str, list[str]]:
    # Match the older test pipeline defaults because they are slower but much
    # more predictable across Windows laptops and mixed driver setups.
    # CRF 23 is the standard balance between quality and file size.
    return "libx264", ["-preset", "medium", "-crf", "28", "-pix_fmt", "yuv420p"]


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
    return subtitle_region_detected(subtitle_region)


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
        # CQ 23-24 for NVENC is roughly equivalent to CRF 23 for x264
        return "h264_nvenc", ["-preset", "p5", "-rc", "vbr", "-cq", "28", "-pix_fmt", "yuv420p"]
    return stable_video_codec()


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
) -> None:
    codec, codec_args = choose_video_codec()
    font_size = int(subtitle_preset.get("fontSize", 18))
    effective_region = resolve_subtitle_region_for_position(video_meta=get_video_meta(video_path), subtitle_region=subtitle_region, subtitle_preset=subtitle_preset)
    margin_v = int(effective_region.get("marginV", subtitle_preset.get("bottomOffset", 36)))
    cleanup_blur_strength = max(
        2,
        min(
            int(subtitle_preset.get("cleanupBlurStrength", subtitle_region.get("blurStrength", 10))),
            24,
        ),
    )
    blur_filter = (
        f"boxblur=luma_radius={cleanup_blur_strength}:luma_power=1,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.34:t=fill"
    )
    primary_color = subtitle_preset.get("assPrimaryColor") or "&H0038D8FF"
    outline_color = subtitle_preset.get("assOutlineColor") or "&H00000000"
    outline = int(subtitle_preset.get("strokeWidth", 2))

    if use_ass:
        subtitles_filter = f"ass={subtitles_path.relative_to(ROOT).as_posix()}"
    else:
        subtitles_filter = (
            f"subtitles={subtitles_path.relative_to(ROOT).as_posix()}:"
            f"force_style='FontName=Arial,PrimaryColour={primary_color},"
            f"OutlineColour={outline_color},BorderStyle=1,Outline={outline},Shadow=0,"
            f"FontSize={font_size},BackColour=&H00000000,MarginV={margin_v},Alignment=2'"
        )

    region_x = int(effective_region.get("x", 0))
    region_y = int(effective_region.get("y", 0))
    region_w = int(effective_region.get("w", 0))
    region_h = int(effective_region.get("h", 0))

    dynamic_regions = [region for region in (dynamic_regions or []) if int(region.get("w", 0)) > 0 and int(region.get("h", 0)) > 0]

    # When there are too many dynamic regions, the filter_complex chain becomes
    # extremely heavy (each region adds split→crop→blur→overlay) and can cause
    # FFmpeg to hang indefinitely on the first frame.  Fall back to a single
    # static blur region that covers the whole subtitle area for the entire
    # video duration.
    MAX_DYNAMIC_REGIONS = 30
    if len(dynamic_regions) > MAX_DYNAMIC_REGIONS:
        print(f"[warn] {len(dynamic_regions)} dynamic regions detected – collapsing to static region to avoid FFmpeg hang.", flush=True)
        dynamic_regions = []

    if dynamic_regions:
        if cleanup_mode == "localized_blur":
            filter_parts: list[str] = []
            current_label = "v0"
            filter_parts.append(f"[0:v]null[{current_label}]")
            for idx, region in enumerate(dynamic_regions, start=1):
                next_label = f"v{idx}"
                start_t = max(int(region.get("startMs", 0)), 0) / 1000
                end_t = max(int(region.get("endMs", 0)), 0) / 1000
                x = max(int(region.get("x", region_x)), 0)
                y = max(int(region.get("y", region_y)), 0)
                w = max(int(region.get("w", region_w)), 1)
                h = max(int(region.get("h", region_h)), 1)
                base_label = f"base{idx}"
                crop_label = f"crop{idx}"
                blur_label = f"blur{idx}"
                filter_parts.append(f"[{current_label}]split=2[{base_label}][{crop_label}]")
                filter_parts.append(
                    f"[{crop_label}]crop=w={w}:h={h}:x={x}:y={y},{blur_filter}[{blur_label}]"
                )
                filter_parts.append(
                    f"[{base_label}][{blur_label}]overlay={x}:{y}:enable='between(t,{start_t:.3f},{end_t:.3f})'[{next_label}]"
                )
                current_label = next_label
            filter_parts.append(f"[{current_label}]{subtitles_filter}[vout]")
            video_filter = ";".join(filter_parts)
            filter_arg = "-filter_complex"
            video_map = "[vout]"
        elif cleanup_mode == "localized_mask":
            drawbox_chain = ",".join(
                [
                    "drawbox="
                    f"x={max(int(region.get('x', region_x)), 0)}:"
                    f"y={max(int(region.get('y', region_y)), 0)}:"
                    f"w={max(int(region.get('w', region_w)), 1)}:"
                    f"h={max(int(region.get('h', region_h)), 1)}:"
                    "color=black@0.68:t=fill:"
                    f"enable='between(t,{max(int(region.get('startMs', 0)), 0) / 1000:.3f},{max(int(region.get('endMs', 0)), 0) / 1000:.3f})'"
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
            video_filter = f"drawbox=x={region_x}:y={region_y}:w={region_w}:h={region_h}:color=black@0.68:t=fill,{subtitles_filter}"
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
        
    temp_script_path: Path | None = None
    if filter_arg == "-filter_complex" and len(video_filter) > 3500:
        temp_script_path = output_path.with_suffix(".ffmpeg-filter.txt")
        temp_script_path.write_text(video_filter, encoding="utf-8")
        command.extend(["-filter_complex_script", str(temp_script_path)])
    else:
        command.extend([filter_arg, video_filter])
    command.extend(
        [
            "-c:v",
            codec,
            *codec_args,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
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
) -> None:
    kwargs = {
        "audio_mix_mode": audio_mix_mode,
        "keep_original_audio": keep_original_audio,
        "background_audio_path": background_audio_path,
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
) -> dict[str, Any]:
    clip_window = select_intro_hook_window(
        segments,
        video_duration_ms=int(video_meta.get("durationMs", 0)),
        desired_clip_ms=int(intro_hook.get("clipDurationMs", 13000)),
    )
    emit_progress(phase="render", step="intro_hook", progress=0.86, message="Đang soạn lời thoại intro (AI)...")
    intro_text = build_intro_hook_text_with_context(
        clip_window["segments"],
        source_language=source_language,
        clip_duration_ms=clip_window["durationMs"],
    )
    emit_progress(phase="render", step="intro_hook", progress=0.87, message="Đang tạo giọng nói intro (TTS)...")
    intro_voice = intro_hook.get("voice") or voice_mapping.get("speaker_1") or DEFAULT_VOICES[0]
    intro_rate_delta_percent = int(intro_hook.get("voiceRateDeltaPercent") or 0)
    clip_path = dirs["render"] / "intro_hook_source.mp4"
    mixed_intro_audio = dirs["audio"] / "intro_hook_audio.wav"
    intro_srt_path = dirs["render"] / "intro_hook.srt"
    teaser_output_path = dirs["render"] / "intro_hook_rendered.mp4"

    extract_video_clip(input_path, clip_path, clip_window["startMs"], clip_window["durationMs"])
    fitted_intro_voice, _, intro_rate, _, _, intro_spoken_text = synthesize_timed_tts_clip(
        index=0,
        speaker_id="intro_hook",
        voice=intro_voice,
        translated=intro_text,
        source_text=intro_text,
        delivery="excited",
        target_ms=max(clip_window["durationMs"] - 120, 1200),
        timing_mode=timing_mode,
        tts_dir=dirs["tts"],
        intro=True,
        rate_delta_percent=intro_rate_delta_percent,
    )
    create_intro_audio(
        video_clip_path=clip_path,
        intro_voice_path=fitted_intro_voice,
        output_path=mixed_intro_audio,
        has_audio=bool(video_meta.get("hasAudio")),
        use_background_audio=bool(intro_hook.get("useBackgroundAudio", True)),
        background_volume=float(intro_hook.get("backgroundVolume", 0.08)),
    )

    if subtitle_enabled:
        intro_subtitles = create_display_subtitles(
            [
                {
                    "translatedText": intro_text,
                    "spokenText": intro_spoken_text,
                    "startMs": 0,
                    "endMs": clip_window["durationMs"],
                }
            ],
            max_words=int(subtitle_preset.get("maxWordsPerChunk", 5)),
            max_chars=int(subtitle_preset.get("maxCharsPerChunk", 22)),
            punctuation_aware=bool(subtitle_preset.get("punctuationAwareSplit", True)),
        )
        intro_dynamic_regions, intro_positions = build_dynamic_subtitle_regions(
            clip_path,
            video_meta=video_meta,
            subtitles=intro_subtitles,
            fallback_region=subtitle_region,
        )
        intro_ass_path = dirs["render"] / "intro_hook.ass"
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
        )
    else:
        mux_video_with_audio(video_path=clip_path, audio_path=mixed_intro_audio, output_path=teaser_output_path)
    return {
        "enabled": True,
        "text": intro_text,
        "spokenText": intro_spoken_text,
        "videoPath": str(teaser_output_path),
        "sourceStartMs": clip_window["startMs"],
        "sourceEndMs": clip_window["endMs"],
        "durationMs": clip_window["durationMs"],
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
            "[0:v:0][0:a:0][1:v:0][1:a:0]concat=n=2:v=1:a=1[v][a]",
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
        
    watermark_input_index = command.index("-i") + 2  # Find next available index. We know command has at least 2 inputs.
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

    wm_filter = f"[{watermark_idx}:v]scale={wm_w}:-1[wm];"
    
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

def mux_video_with_audio(
    *, 
    video_path: Path, 
    audio_path: Path, 
    output_path: Path,
    watermark_options: dict[str, Any] | None = None,
    video_meta: dict[str, Any] | None = None
) -> None:
    codec, codec_args = choose_video_codec()
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
            command, "-vf", "null", "0:v:0", watermark_options, video_meta
        )
        map_idx = command.index("-map")
        # Replace the first map (video)
        command[map_idx+1] = video_map
        command.insert(map_idx, video_filter)
        command.insert(map_idx, filter_arg)
        
    command.extend([
        "-c:v", codec, *codec_args,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ])
    run(command, cwd=ROOT)



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
    ) -> str:
    from src.pyJianYingDraft import (
        AudioMaterial,
        AudioSegment as DraftAudioSegment,
        ClipSettings,
        DraftFolder,
        TextBorder,
        TextSegment,
        TextShadow,
        TextStyle,
        Timerange,
        TrackType,
        VideoMaterial,
        VideoSegment,
    )
    from src.pyJianYingDraft.metadata import FontType

    if not draft_root:
        raise RuntimeError("Draft root is empty. Configure a CapCut draft directory before exporting draft output.")
    draft_folder = DraftFolder(draft_root)
    draft_name = f"{Path(analysis_name).stem}_dubstudio_{time.strftime('%Y%m%d_%H%M%S')}"
    meta_for_draft = get_video_meta(flattened_video_path) if flattened_video_path else video_meta
    fps = max(24, int(round(float(meta_for_draft.get("fps") or 30))))
    script = draft_folder.create_draft(
        draft_name=draft_name,
        width=int(meta_for_draft["width"]),
        height=int(meta_for_draft["height"]),
        fps=fps,
        allow_replace=True,
    )
    if flattened_video_path:
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
        audio_material = AudioMaterial(str(flattened_video_path))
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
    subtitle_enabled = bool(subtitle_preset.get("enabled", True))
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
    draft_font = getattr(FontType, str(subtitle_preset.get("draftFontKey") or "").strip(), None)
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
                shadow=shadow,
            )
            script.add_segment(text_segment, "vietsub_track")

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
            "fontSize": 28,
            "fontFamily": "arial-bold",
            "fontFamilyLabel": "Arial Bold",
            "fontFamilyName": "Arial",
            "cssFontFamily": "\"Arial Black\", Arial, sans-serif",
            "assFontName": "Arial",
            "draftFontKey": "Poppins_Bold",
            "fontColor": "#ffd200",
            "strokeColor": "#000000",
            "strokeWidth": 2,
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
        "keepOriginalAudio": True,
        "draftRoot": "",
        "outputDirectory": "",
        "introHook": {
            "enabled": True,
            "clipDurationMs": 10000,
            "voice": DEFAULT_VOICES[0],
            "voicePresetKey": "edge:male",
            "voiceRateDeltaPercent": 0,
            "useBackgroundAudio": True,
            "backgroundVolume": 0.08,
        },
    }


ANALYSIS_CACHE_VERSION = 2


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
    
    merged_segments = whisperx_analysis.get("mergedSegments")
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
                "spokenText": "",
                "delivery": "neutral",
                "subtitleChunks": split_display_text(subtitle_text),
            }
        )

    try:
        local_speaker_llm_available = bool(
            should_use_ollama(DUB_TRANSLATE_PROVIDER) or should_use_llama_cpp(DUB_TRANSLATE_PROVIDER)
        )
    except Exception:
        local_speaker_llm_available = False
    if local_speaker_llm_available and (
        speaker_count <= 1 or voice_layout == "single_voice" or speaker_confidence < 0.56
    ):
        emit_progress(
            phase="analysis",
            step="speaker_refinement",
            progress=0.63,
            message="Đang dùng Gemma 4 suy luận lại số nhân vật từ transcript",
        )
        (
            segments,
            speaker_count,
            speaker_confidence,
            voice_layout,
            upgraded_stats,
            upgraded_main_speaker_id,
            speaker_upgrade_note,
        ) = maybe_upgrade_speaker_segmentation_with_llm(
            segments,
            speaker_count=speaker_count,
            speaker_confidence=speaker_confidence,
            voice_layout=voice_layout,
            provider=DUB_TRANSLATE_PROVIDER,
        )
        if upgraded_stats:
            speaker_stats = upgraded_stats
            main_speaker_id = upgraded_main_speaker_id or main_speaker_id
            sample_paths = extract_speaker_samples(
                input_path,
                segments,
                dirs["analysis"] / "speakers",
            )
        if speaker_upgrade_note:
            whisperx_analysis.setdefault("warnings", []).append(speaker_upgrade_note)

    refinement = {}
    if speaker_count > 1 and local_speaker_llm_available:
        emit_progress(phase="analysis", step="speaker_refinement", progress=0.65, message="Đang nhận diện vai trò nhân vật bằng AI")
        refinement = refine_speakers_with_ollama(segments, [f"speaker_{i+1}" for i in range(speaker_count)])

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
                "spokenText": "",
                "delivery": "neutral",
                "subtitleChunks": split_display_text(subtitle_text),
            }
        )
    try:
        local_speaker_llm_available = bool(
            should_use_ollama(DUB_TRANSLATE_PROVIDER) or should_use_llama_cpp(DUB_TRANSLATE_PROVIDER)
        )
    except Exception:
        local_speaker_llm_available = False
    if local_speaker_llm_available and (
        speaker_count <= 1 or voice_layout == "single_voice" or speaker_confidence < 0.56
    ):
        emit_progress(
            phase="analyze",
            step="speaker_refinement",
            progress=0.63,
            message="Đang dùng Gemma 4 suy luận lại số nhân vật từ transcript",
        )
        (
            segments,
            speaker_count,
            speaker_confidence,
            voice_layout,
            upgraded_stats,
            upgraded_main_speaker_id,
            speaker_upgrade_note,
        ) = maybe_upgrade_speaker_segmentation_with_llm(
            segments,
            speaker_count=speaker_count,
            speaker_confidence=speaker_confidence,
            voice_layout=voice_layout,
            provider=DUB_TRANSLATE_PROVIDER,
        )
        if upgraded_stats:
            speaker_stats = upgraded_stats
            main_speaker_id = upgraded_main_speaker_id or main_speaker_id
            sample_paths = extract_speaker_samples(
                input_path,
                segments,
                dirs["analysis"] / "speakers",
            )
        if speaker_upgrade_note:
            transcription.setdefault("warnings", []).append(speaker_upgrade_note)

    refinement = {}
    if speaker_count > 1 and local_speaker_llm_available:
        emit_progress(phase="analysis", step="speaker_refinement", progress=0.65, message="Đang nhận diện vai trò nhân vật bằng AI")
        refinement = refine_speakers_with_ollama(segments, [f"speaker_{i+1}" for i in range(speaker_count)])

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

    emit_progress(phase="render", step="prepare", progress=0.08, message="Đang chuẩn bị dữ liệu render")
    os.environ["CAPCUT_VIDEO_CODEC_MODE"] = video_codec_mode
    print(f"Using video codec mode: {video_codec_mode}", flush=True)
    print(f"Using video codec: {choose_video_codec()[0]}", flush=True)
    translated_cache_path = dirs["analysis"] / "translated.json"
    editable_subtitle_timeline = analysis.get("subtitleTimeline") or []
    segments = (
        apply_subtitle_timeline_to_segments(analysis["segments"], editable_subtitle_timeline)
        if editable_subtitle_timeline
        else copy.deepcopy(analysis["segments"])
    )
    segments = translate_segments(
        segments,
        source_language,
        translated_cache_path,
        target_language=target_language,
        phase="render",
    )
    subtitle_timeline = (
        editable_subtitle_timeline if editable_subtitle_timeline else build_subtitle_timeline(segments)
    )
    display_subtitles: list[SubtitleLine] = subtitle_timeline_to_lines(subtitle_timeline)
    dynamic_regions: list[dict[str, Any]] = []
    subtitle_positions: list[dict[str, int]] = []
    subtitle_ass_path = dirs["render"] / "vietsub_display.ass"
    subtitle_srt_path = dirs["render"] / "vietsub_display.srt"
    if subtitle_enabled:
        dynamic_regions, subtitle_positions = build_dynamic_subtitle_regions(
            input_path,
            video_meta=analysis["videoMeta"],
            subtitles=display_subtitles,
            fallback_region=effective_subtitle_region,
        )
        cleanup_mode = resolve_source_subtitle_cleanup_mode(
            requested_cleanup_mode,
            subtitle_region=analysis.get("subtitleRegion", {}),
            dynamic_regions=dynamic_regions,
        )
        subtitle_ass_path.write_text(
            compose_ass(
                display_subtitles,
                video_meta=analysis["videoMeta"],
                subtitle_preset=subtitle_preset,
                subtitle_positions=subtitle_positions,
            ),
            encoding="utf-8-sig",
        )
        subtitle_srt_path.write_text(
            compose_srt_from_timeline(subtitle_timeline), encoding="utf-8-sig"
        )
    else:
        cleanup_mode = resolve_source_subtitle_cleanup_mode(
            requested_cleanup_mode,
            subtitle_region=analysis.get("subtitleRegion", {}),
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
    )

    outputs: dict[str, Any] = {
        "jobId": analysis["jobId"],
        "previewVideoPath": "",
        "outputVideoPath": "",
        "draftPath": "",
        "dubAudioPath": str(dub_audio_path),
        "mixedAudioPath": str(mixed_audio_path),
        "backgroundAudioPath": str(background_audio_path) if background_audio_path else "",
        "subtitlePath": str(subtitle_ass_path) if subtitle_enabled else "",
        "subtitleSrtPath": str(subtitle_srt_path) if subtitle_enabled else "",
        "manifestPath": str(manifest_path),
        "warnings": list(analysis.get("warnings", [])) + background_warnings,
        "introHook": {"enabled": False},
        "outputDirectory": output_directory,
    }

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
            )
        else:
            mux_video_with_audio(video_path=input_path, audio_path=mixed_audio_path, output_path=main_render_path, watermark_options=subtitle_preset.get("watermarkOptions"), video_meta=analysis["videoMeta"])

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

    if output_targets.get("draft", True):
        try:
            emit_progress(phase="render", step="draft", progress=0.9, message="Đang tạo draft CapCut")
            outputs["draftPath"] = create_capcut_draft(
                draft_root=draft_root,
                video_path=input_path,
                dub_audio_path=dub_audio_path,
                subtitles=display_subtitles,
                subtitle_preset=subtitle_preset,
                subtitle_region=effective_subtitle_region,
                video_meta=analysis["videoMeta"],
                analysis_name=Path(input_path).stem,
                flattened_video_path=flattened_render_path,
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
    preview_text = normalize_text(text) or "Xin chào, đây là giọng lồng tiếng thử nghiệm của mình. Bạn thấy có tự nhiên không?"
    selected_voice = resolve_voice_preset(voice)
    extension = resolve_tts_output_extension(
        voice=selected_voice,
        speaker_id=speaker_id or "speaker_1",
        job_id=job_id or "",
    )
    preview_dir = ensure_dir(DUB_STUDIO_DIR / "voice_preview")
    cache_key = hashlib.sha1(
        f"{selected_voice}|{speaker_id}|{job_id}|{preview_text}".encode("utf-8", errors="ignore")
    ).hexdigest()[:16]
    output_path = preview_dir / f"{speaker_id}_{cache_key}{extension}"
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
    result = {
        "voice": selected_voice,
        "speakerId": speaker_id or "speaker_1",
        "outputPath": str(output_path),
        "text": preview_text,
    }
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
