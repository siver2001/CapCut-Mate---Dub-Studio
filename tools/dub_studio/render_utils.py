from __future__ import annotations

from typing import Any

from .models import SubtitleLine
from .subtitle_utils import normalize_text

SUBTITLE_PREVIEW_REFERENCE_HEIGHT = 360


def subtitle_preview_to_video_px(value: int | float, video_meta: dict[str, Any]) -> int:
    video_height = max(int(video_meta.get("height") or 1920), 1)
    return max(int(round(float(value) * video_height / SUBTITLE_PREVIEW_REFERENCE_HEIGHT)), 0)


def subtitle_preview_offset(position_preset: str, bottom_offset: int) -> float:
    safe_offset = max(int(bottom_offset), 0)
    if position_preset == "top":
        return 32.0 + safe_offset * 0.35
    if position_preset == "middle":
        return 0.0
    return max(safe_offset, 12) * 0.7


def effective_ass_font_size(
    subtitle_preset: dict[str, Any],
    video_meta: dict[str, Any],
) -> int:
    return max(subtitle_preview_to_video_px(int(subtitle_preset.get("fontSize", 18)), video_meta), 8)


def effective_ass_outline(value: int | float, video_meta: dict[str, Any]) -> int:
    if float(value or 0) <= 0:
        return 0
    return max(subtitle_preview_to_video_px(value, video_meta), 1)


def effective_ass_margin_v(
    subtitle_preset: dict[str, Any],
    video_meta: dict[str, Any],
) -> int:
    position_preset = str(subtitle_preset.get("positionPreset") or "bottom").strip().lower()
    preview_offset = subtitle_preview_offset(
        position_preset,
        int(subtitle_preset.get("bottomOffset", 54)),
    )
    return subtitle_preview_to_video_px(preview_offset, video_meta)


def default_subtitle_region(video_meta: dict[str, Any]) -> dict[str, Any]:
    width = int(video_meta["width"])
    height = int(video_meta["height"])
    # Thu hẹp vùng làm mờ từ 0.8 -> 0.85 chiều rộng để phủ tốt hơn
    region_width = int(width * 0.85)
    region_height = int(height * 0.052) if height > width else 90
    region_height = max(min(region_height, 120), 60)
    
    x = int((width - region_width) / 2)
    # Tự động điều chỉnh vị trí mặc định dựa trên tỷ lệ khung hình
    if height > width:
        # Video dọc (TikTok/Douyin): Sub thường ở khoảng 70-80% chiều cao
        y = int(height * 0.72)
    else:
        # Video ngang: Sub thường ở khoảng 85% chiều cao
        y = int(height * 0.82)
        
    return {
        "detected": False,
        "cleanupMode": "localized_blur",
        "blurStrength": 20,
        "x": x,
        "y": y,
        "w": region_width,
        "h": region_height,
        "centerX": x + region_width // 2,
        "centerY": y + region_height // 2,
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
    if resolved.get("detected") or "y" in resolved:
        y = max(min(int(resolved.get("y", fallback["y"])), max(height - region_h, 0)), 0)
    else:
        y = max(min(int(fallback["y"]), max(height - region_h, 0)), 0)
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


def hex_to_ass_color(hex_color: str, alpha: float | None = None) -> str:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        return "&H00FFFFFF"
    red = value[0:2]
    green = value[2:4]
    blue = value[4:6]
    if alpha is None:
        alpha_hex = "00"
    else:
        safe_alpha = max(0.0, min(float(alpha), 1.0))
        alpha_hex = f"{int(round((1.0 - safe_alpha) * 255)):02X}"
    return f"&H{alpha_hex}{blue}{green}{red}".upper()


def get_text_pixel_size(text: str, font_name: str, font_size: int) -> tuple[int, int]:
    try:
        from PIL import ImageFont
        font_paths = [
            f"{font_name}.ttf",
            f"C:/Windows/Fonts/{font_name}.ttf",
            f"C:/Windows/Fonts/{font_name}bd.ttf",
            f"C:/Windows/Fonts/Arial.ttf",
        ]
        font = None
        for path in font_paths:
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
            
        lines = text.split(r"\N") if r"\N" in text else text.split("\n")
        max_w = 0
        total_h = 0
        line_h = font_size
        
        for line in lines:
            if hasattr(font, "getmask"):
                bbox = font.getmask(line).getbbox()
                if bbox:
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                    max_w = max(max_w, w)
                    total_h += h
                    line_h = max(line_h, h)
                else:
                    max_w = max(max_w, font_size * len(line) // 2)
                    total_h += font_size
            else:
                max_w = max(max_w, font_size * len(line) // 2)
                total_h += font_size
                
        if len(lines) > 1:
            total_h += (len(lines) - 1) * int(line_h * 0.3)
            
        return max_w, total_h
    except Exception:
        return font_size * len(text) // 2, font_size


def compose_ass(
    lines: list[SubtitleLine],
    *,
    video_meta: dict[str, Any],
    subtitle_preset: dict[str, Any],
    subtitle_positions: list[dict[str, int]] | None = None,
) -> str:
    font_size = effective_ass_font_size(subtitle_preset, video_meta)
    ass_font_name = subtitle_preset.get("assFontName") or subtitle_preset.get("fontFamilyName") or "Arial"
    font_tokens = " ".join(
        str(part or "")
        for part in (
            subtitle_preset.get("fontFamily"),
            subtitle_preset.get("fontFamilyLabel"),
            subtitle_preset.get("fontFamilyName"),
            ass_font_name,
        )
    ).lower()
    bold_flag = -1 if "bold" in font_tokens or "black" in font_tokens else 0
    primary_color = subtitle_preset.get("assPrimaryColor") or hex_to_ass_color(subtitle_preset.get("fontColor", "#ffd200"))
    outline_color = subtitle_preset.get("assOutlineColor") or hex_to_ass_color(subtitle_preset.get("strokeColor", "#000000"))
    outline = effective_ass_outline(int(subtitle_preset.get("strokeWidth", 2)), video_meta)
    box_enabled = bool(subtitle_preset.get("boxEnabled", False))
    box_fill_color = subtitle_preset.get("assBoxFillColor") or hex_to_ass_color(
        subtitle_preset.get("boxFillColor", "#77b8ee"),
        float(subtitle_preset.get("boxFillOpacity", 0.86)),
    )
    box_border_color = subtitle_preset.get("assBoxBorderColor") or hex_to_ass_color(
        subtitle_preset.get("boxBorderColor", "#3b82f6"),
        float(subtitle_preset.get("boxBorderOpacity", 1.0)),
    )
    box_border_width = effective_ass_outline(
        max(int(subtitle_preset.get("boxBorderWidth", 2)), 0),
        video_meta,
    )
    box_padding_x = max(int(subtitle_preset.get("boxPaddingX", 24)), 0)
    box_padding_y = max(int(subtitle_preset.get("boxPaddingY", 12)), 0)
    box_radius = max(int(subtitle_preset.get("boxRadius", 16)), 0)

    position_preset = str(subtitle_preset.get("positionPreset") or "bottom").strip().lower()
    alignment = 8 if position_preset == "top" else 5 if position_preset == "middle" else 2
    margin_v = effective_ass_margin_v(subtitle_preset, video_meta)
    
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
        (
            f"Style: DubDefault,{ass_font_name},{font_size},{primary_color},{primary_color},"
            f"{outline_color},{outline_color},"
            f"{bold_flag},0,0,0,100,100,0,0,1,"
            f"{outline},0,{alignment},0,0,{margin_v},1"
        ),
    ]

    if box_enabled:
        lines_out.append(
            f"Style: DubBox,Arial,{font_size},{box_fill_color},{box_fill_color},"
            f"{box_border_color},{box_border_color},"
            f"0,0,0,0,100,100,0,0,1,"
            f"{box_border_width},0,{alignment},0,0,{margin_v},1"
        )

    lines_out.extend([
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ])
    
    subtitle_positions = subtitle_positions or []
    res_x = int(video_meta.get('width', 1080))
    res_y = int(video_meta.get('height', 1920))

    for idx, item in enumerate(lines):
        content = escape_ass_text(item.content)
        position = subtitle_positions[idx] if idx < len(subtitle_positions) else None
        
        w, h = get_text_pixel_size(content, ass_font_name, font_size)
        
        if position:
            cx = int(position['centerX'])
            cy = int(position['centerY']) - max(int(font_size * 0.12), 4)
        else:
            cx = res_x // 2
            if alignment == 8:
                cy = margin_v + h // 2
            elif alignment == 5:
                cy = res_y // 2
            else:
                cy = res_y - margin_v - h // 2

        # Prevent text from bleeding off the screen edges
        cx = max(w // 2 + 30, min(cx, res_x - w // 2 - 30))
        cy = max(h // 2 + 20, min(cy, res_y - h // 2 - 20))

        if box_enabled:
            # Draw dynamic rounded rectangle vector at absolute coordinates
            W = w + 2 * box_padding_x
            H = h + 2 * box_padding_y
            x1 = cx - w / 2 - box_padding_x
            y1 = cy - h / 2 - box_padding_y
            r = min(box_radius, int(min(W, H) / 2))
            
            # Bézier rounded rectangle path starting from (0, 0) up to (W, H)
            box_commands = (
                f"m {int(r)} 0 "
                f"l {int(W - r)} 0 "
                f"b {int(W - r/2)} 0 {int(W)} {int(r/2)} {int(W)} {int(r)} "
                f"l {int(W)} {int(H - r)} "
                f"b {int(W)} {int(H - r/2)} {int(W - r/2)} {int(H)} {int(W - r)} {int(H)} "
                f"l {int(r)} {int(H)} "
                f"b {int(r/2)} {int(H)} 0 {int(H - r/2)} 0 {int(H - r)} "
                f"l 0 {int(r)} "
                f"b 0 {int(r/2)} {int(r/2)} 0 {int(r)} 0"
            )
            
            lines_out.append(
                "Dialogue: 0,"
                f"{format_ass_timestamp(item.start_ms)},"
                f"{format_ass_timestamp(item.end_ms)},"
                f"DubBox,,0,0,0,,{{\\an7\\pos({int(x1)},{int(y1)})\\p1}}{box_commands}{{\\p0}}"
            )
            
            lines_out.append(
                "Dialogue: 1,"
                f"{format_ass_timestamp(item.start_ms)},"
                f"{format_ass_timestamp(item.end_ms)},"
                f"DubDefault,,0,0,0,,{{\\an5\\pos({cx},{cy})}}{content}"
            )
        else:
            pos_tag = rf"{{\an5\pos({cx},{cy})}}"
            lines_out.append(
                "Dialogue: 0,"
                f"{format_ass_timestamp(item.start_ms)},"
                f"{format_ass_timestamp(item.end_ms)},"
                f"DubDefault,,0,0,0,,{pos_tag}{content}"
            )
    return "\n".join(lines_out) + "\n"
