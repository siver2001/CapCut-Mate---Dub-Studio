from __future__ import annotations

from pathlib import Path

from .config import ROOT
from .io_utils import run


def burn_subtitles(
    video_path: Path,
    audio_path: Path,
    subtitles_path: Path,
    output_path: Path,
    cover_source_subtitles: bool,
    subtitle_font_size: int,
    subtitle_color: str = "&H0038D8FF",
    subtitle_outline_color: str = "&H00000000",
    subtitle_margin_v: int = 54,
    source_subtitle_mask_mode: str = "black",
    subtitle_font_name: str = "Arial",
) -> None:
    subtitles_filter = (
        f"subtitles={subtitles_path.relative_to(ROOT).as_posix()}:"
        f"force_style='FontName={subtitle_font_name},PrimaryColour={subtitle_color},"
        f"OutlineColour={subtitle_outline_color},BorderStyle=1,Outline=2,Shadow=0,"
        f"FontSize={subtitle_font_size},BackColour=&H00000000,MarginV={subtitle_margin_v},Alignment=2'"
    )
    if cover_source_subtitles and source_subtitle_mask_mode == "blur":
        video_filter = (
            "[0:v]split=2[base][masksrc];"
            "[masksrc]crop=w=760:h=108:x=(iw-760)/2:y=930,boxblur=luma_radius=14:luma_power=2[mask];"
            f"[base][mask]overlay=(W-w)/2:930[masked];[masked]{subtitles_filter}[vout]"
        )
        filter_arg = "-filter_complex"
        video_map = "[vout]"
    else:
        filters: list[str] = []
        if cover_source_subtitles:
            filters.append("drawbox=x=0:y=872:w=iw:h=208:color=black@1.0:t=fill")
        filters.append(subtitles_filter)
        video_filter = ",".join(filters)
        filter_arg = "-vf"
        video_map = "0:v:0"
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            video_map,
            "-map",
            "1:a:0",
            filter_arg,
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ],
        cwd=ROOT,
    )
