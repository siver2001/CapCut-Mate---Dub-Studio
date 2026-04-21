from __future__ import annotations

from typing import Any

from .models import SubtitleLine
from .subtitle_utils import normalize_text


def default_subtitle_region(video_meta: dict[str, Any]) -> dict[str, Any]:
    width = int(video_meta["width"])
    height = int(video_meta["height"])
    # Thu hẹp vùng làm mờ từ 0.68 -> 0.45 chiều rộng để không quá rộng
    region_width = int(width * 0.45)
    # Giảm chiều cao từ 0.085 -> 0.05 và min = 60 để không quá to
    region_height = int(max(height * 0.05, 60))
    x = max((width - region_width) // 2, 0)
    # Tinh chỉnh lại vị trí Y để nằm sát dưới hơn một chút, bớt che video
    y = max(height - region_height - int(height * 0.04), 0)
    return {
        "detected": False,
        "cleanupMode": "localized_blur",
        "blurStrength": 10,
        "x": x,
        "y": y,
        "w": region_width,
        "h": region_height,
        "normalized": {
            "x": round(x / width, 4),
            "y": round(y / height, 4),
            "w": round(region_width / width, 4),
            "h": round(region_height / height, 4),
        },
    }


def resolve_subtitle_region_for_position(
    video_meta: dict[str, Any],
    subtitle_region: dict[str, Any],
    subtitle_preset: dict[str, Any],
) -> dict[str, Any]:
    width = int(video_meta.get("width") or 1080)
    height = int(video_meta.get("height") or 1920)
    fallback = default_subtitle_region(video_meta)
    resolved = {**fallback, **(subtitle_region or {})}
    region_w = max(min(int(resolved.get("w", fallback["w"])), width), 1)
    region_h = max(min(int(resolved.get("h", fallback["h"])), height), 1)
    x = max(min(int(resolved.get("x", fallback["x"])), max(width - region_w, 0)), 0)
    if resolved.get("detected"):
        y = max(min(int(resolved.get("y", fallback["y"])), max(height - region_h, 0)), 0)
    else:
        position_preset = str(subtitle_preset.get("positionPreset") or "bottom").strip().lower()
        bottom_offset = max(int(subtitle_preset.get("bottomOffset", 54)), 12)
        if position_preset == "top":
            y = int(height * 0.08)
        elif position_preset == "middle":
            y = max((height - region_h) // 2, 0)
        else:
            y = max(height - region_h - bottom_offset, 0)
        y = max(min(y, max(height - region_h, 0)), 0)
    margin_v = max(height - y - region_h, 0)
    return {
        **resolved,
        "x": x,
        "y": y,
        "w": region_w,
        "h": region_h,
        "marginV": margin_v,
        "normalized": {
            "x": round(x / max(width, 1), 4),
            "y": round(y / max(height, 1), 4),
            "w": round(region_w / max(width, 1), 4),
            "h": round(region_h / max(height, 1), 4),
        },
    }


def format_ass_timestamp(milliseconds: int) -> str:
    total_centiseconds = max(milliseconds // 10, 0)
    hours = total_centiseconds // 360000
    minutes = (total_centiseconds % 360000) // 6000
    seconds = (total_centiseconds % 6000) // 100
    centiseconds = total_centiseconds % 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def escape_ass_text(text: str) -> str:
    return (
        normalize_text(text)
        .replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def hex_to_ass_color(hex_color: str) -> str:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        return "&H00FFFFFF"
    red = value[0:2]
    green = value[2:4]
    blue = value[4:6]
    return f"&H00{blue}{green}{red}".upper()


def compose_ass(
    lines: list[SubtitleLine],
    *,
    video_meta: dict[str, Any],
    subtitle_preset: dict[str, Any],
    subtitle_positions: list[dict[str, int]] | None = None,
) -> str:
    font_size = int(subtitle_preset.get("fontSize", 18))
    ass_font_name = subtitle_preset.get("assFontName") or subtitle_preset.get("fontFamilyName") or "Arial"
    primary_color = subtitle_preset.get("assPrimaryColor") or hex_to_ass_color(subtitle_preset.get("fontColor", "#ffd200"))
    outline_color = subtitle_preset.get("assOutlineColor") or hex_to_ass_color(subtitle_preset.get("strokeColor", "#000000"))
    outline = int(subtitle_preset.get("strokeWidth", 2))
    position_preset = str(subtitle_preset.get("positionPreset") or "bottom").strip().lower()
    alignment = 8 if position_preset == "top" else 5 if position_preset == "middle" else 2
    margin_v = int(
        resolve_subtitle_region_for_position(video_meta, default_subtitle_region(video_meta), subtitle_preset).get(
            "marginV",
            36,
        )
    )
    lines_out = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {int(video_meta.get('width', 1080))}",
        f"PlayResY: {int(video_meta.get('height', 1920))}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: DubDefault,{ass_font_name},{font_size},{primary_color},{primary_color},{outline_color},&H00000000,0,0,0,0,100,100,0,0,1,{outline},0,{alignment},0,0,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    subtitle_positions = subtitle_positions or []
    for idx, item in enumerate(lines):
        position = subtitle_positions[idx] if idx < len(subtitle_positions) else None
        pos_tag = ""
        if position:
            pos_tag = rf"{{\an5\pos({int(position['centerX'])},{int(position['centerY'])})}}"
        lines_out.append(
            "Dialogue: 0,"
            f"{format_ass_timestamp(item.start_ms)},"
            f"{format_ass_timestamp(item.end_ms)},"
            f"DubDefault,,0,0,0,,{pos_tag}{escape_ass_text(item.content)}"
        )
    return "\n".join(lines_out) + "\n"
