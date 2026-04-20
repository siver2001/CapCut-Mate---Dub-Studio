import json
import asyncio
from typing import List, Dict, Any, Tuple, Optional, Literal
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, TrackType, TextSegment, TextStyle, ClipSettings, Timerange, FontType, TextBorder, TextShadow
from src.pyJianYingDraft.metadata import TextIntro, TextOutro, TextLoopAnim
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
from src.schemas.add_captions import ShadowInfo
from src.service.get_text_effects import resolve_text_effect
from src.utils.draft_lock_manager import DraftLockManager


def add_captions(
    draft_url: str,
    captions: str,
    text_color: str = "#ffffff",
    border_color: Optional[str] = None,
    alignment: int = 1,
    alpha: float = 1.0,
    font: Optional[str] = None,
    font_size: int = 15,
    letter_spacing: Optional[float] = None,
    line_spacing: Optional[float] = None,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: float = 0.0,
    transform_y: float = 0.0,
    style_text: bool = False,
    underline: bool = False,
    italic: bool = False,
    bold: bool = False,
    has_shadow: bool = False,
    shadow_info: Optional[ShadowInfo] = None,
    text_effect: Optional[str] = None
) -> Tuple[str, str, List[str], List[str], List[dict]]:
    """
    Business logic for adding captions to CapCut draft (Synchronous version).
    """
    logger.info(f"add_captions started, draft_url: {draft_url}")
    
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    caption_items = parse_captions_data(captions)
    if not caption_items:
        raise CustomException(CustomError.INVALID_CAPTION_INFO)

    script: ScriptFile = DRAFT_CACHE[draft_id]
    track_name = f"caption_track_{helper.gen_unique_id()}"
    script.add_track(track_type=TrackType.text, track_name=track_name)

    text_ids = []
    segment_ids = []
    segment_infos = []

    for item in caption_items:
        try:
            segment_id, text_id, segment_info = add_caption_to_draft(
                script, track_name,
                caption=item,
                text_color=text_color,
                border_color=border_color,
                alignment=alignment,
                alpha=alpha,
                font=font,
                font_size=font_size,
                letter_spacing=letter_spacing,
                line_spacing=line_spacing,
                scale_x=scale_x,
                scale_y=scale_y,
                transform_x=transform_x,
                transform_y=transform_y,
                style_text=style_text,
                underline=underline,
                italic=italic,
                bold=bold,
                has_shadow=has_shadow,
                shadow_info=shadow_info,
                text_effect=text_effect
            )
            text_ids.append(text_id)
            segment_ids.append(segment_id)
            segment_infos.append(segment_info)
        except Exception as e:
            logger.error(f"Failed to add caption: {str(e)}")

    script.save()
    
    track_id = ""
    for track in script.tracks.values():
        if track.name == track_name:
            track_id = track.track_id
            break

    return draft_url, track_id, text_ids, segment_ids, segment_infos


async def add_captions_async(
    draft_url: str,
    captions: str,
    text_color: str = "#ffffff",
    border_color: Optional[str] = None,
    alignment: int = 1,
    alpha: float = 1.0,
    font: Optional[str] = None,
    font_size: int = 15,
    letter_spacing: Optional[float] = None,
    line_spacing: Optional[float] = None,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: float = 0.0,
    transform_y: float = 0.0,
    style_text: bool = False,
    underline: bool = False,
    italic: bool = False,
    bold: bool = False,
    has_shadow: bool = False,
    shadow_info: Optional[ShadowInfo] = None,
    text_effect: Optional[str] = None,
    lock_timeout: float = 30.0
) -> Tuple[str, str, List[str], List[str], List[dict]]:
    """Async version of add_captions with draft lock protection."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return add_captions(
            draft_url=draft_url, captions=captions, text_color=text_color,
            border_color=border_color, alignment=alignment, alpha=alpha,
            font=font, font_size=font_size, letter_spacing=letter_spacing,
            line_spacing=line_spacing, scale_x=scale_x, scale_y=scale_y,
            transform_x=transform_x, transform_y=transform_y, style_text=style_text,
            underline=underline, italic=italic, bold=bold, has_shadow=has_shadow,
            shadow_info=shadow_info, text_effect=text_effect
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout acquiring lock for draft {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)


def add_caption_to_draft(
    script: ScriptFile,
    track_name: str,
    caption: dict,
    text_color: str = "#ffffff",
    border_color: Optional[str] = None,
    alignment: int = 1,
    alpha: float = 1.0,
    font: Optional[str] = None,
    font_size: int = 15,
    letter_spacing: Optional[float] = None,
    line_spacing: Optional[float] = None,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: float = 0.0,
    transform_y: float = 0.0,
    style_text: bool = False,
    underline: bool = False,
    italic: bool = False,
    bold: bool = False,
    has_shadow: bool = False,
    shadow_info: Optional[ShadowInfo] = None,
    text_effect: Optional[str] = None
) -> Tuple[str, str, dict]:
    """Add a single caption segment to a track."""
    timerange = Timerange(start=caption['start'], duration=caption['end'] - caption['start'])
    rgb_color = hex_to_rgb(text_color)
    
    # Text Style
    text_style = TextStyle(
        size=float(caption.get('font_size', font_size)),
        color=rgb_color,
        alpha=alpha,
        align=alignment if alignment in [0, 1, 2] else 1,
        letter_spacing=int(letter_spacing or 0),
        line_spacing=int(line_spacing or 0),
        underline=underline,
        italic=italic,
        bold=bold
    )

    text_border = TextBorder(color=hex_to_rgb(border_color)) if border_color else None
    font_type = getattr(FontType, font, None) if font else None
    
    text_shadow = None
    if has_shadow:
        if shadow_info:
            text_shadow = TextShadow(
                alpha=shadow_info.shadow_alpha,
                color=hex_to_rgb(shadow_info.shadow_color),
                diffuse=shadow_info.shadow_diffuse,
                distance=shadow_info.shadow_distance,
                angle=shadow_info.shadow_angle
            )
        else:
            text_shadow = TextShadow(color=(0, 0, 0), alpha=0.9, diffuse=15.0, distance=5.0, angle=-45.0)

    clip_settings = ClipSettings(
        scale_x=scale_x, scale_y=scale_y,
        transform_x=transform_x / script.width,
        transform_y=transform_y / script.height
    )

    text_segment = TextSegment(
        text=caption['text'],
        timerange=timerange,
        style=text_style,
        border=text_border,
        font=font_type,
        shadow=text_shadow,
        clip_settings=clip_settings
    )

    # Effects and Animations
    eff_id = caption.get('text_effect') or text_effect
    if eff_id:
        res = resolve_text_effect(eff_id)
        if res:
            text_segment.add_effect(res['effect_id'])

    if caption.get('keyword'):
        apply_keyword_highlight(
            text_segment, caption['keyword'],
            hex_to_rgb(caption.get('keyword_color', '#ff7100')),
            caption.get('keyword_font_size'),
            hex_to_rgb(caption.get('keyword_border_color')) if caption.get('keyword_border_color') else (hex_to_rgb(border_color) if border_color else None)
        )

    for anim_type in ["in", "out", "loop"]:
        anim_name = caption.get(f'{anim_type}_animation')
        if anim_name:
            anim_enum = map_animation_name_to_enum(anim_name, anim_type)
            if anim_enum:
                text_segment.add_animation(anim_enum, duration=caption.get(f'{anim_type}_animation_duration'))

    script.add_segment(text_segment, track_name)
    return text_segment.segment_id, text_segment.material_id, {"id": text_segment.segment_id, "start": caption['start'], "end": caption['end']}


def apply_keyword_highlight(text_segment: TextSegment, keywords: str, color: tuple, size: float = None, border_color: tuple = None):
    """Highlight specific keywords within a text segment."""
    for kw in keywords.split('|'):
        kw = kw.strip()
        if not kw: continue
        
        start = 0
        while True:
            start = text_segment.text.find(kw, start)
            if start == -1: break
            
            end = start + len(kw)
            style = {
                "fill": {"alpha": 1.0, "content": {"render_type": "solid", "solid": {"alpha": 1.0, "color": list(color)}}},
                "range": [start, end],
                "size": size or text_segment.style.size,
                "bold": text_segment.style.bold,
                "italic": text_segment.style.italic,
                "underline": text_segment.style.underline
            }
            if border_color:
                style["strokes"] = [{"content": {"solid": {"alpha": 1.0, "color": list(border_color)}}, "width": 0.08}]
            
            text_segment.extra_styles.append(style)
            start = end


def parse_captions_data(json_str: str) -> List[Dict[str, Any]]:
    """Parse caption metadata from JSON string."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, list): return []
        
        result = []
        for item in data:
            if all(k in item for k in ["start", "end", "text"]):
                result.append({
                    "start": item["start"],
                    "end": item["end"],
                    "text": item["text"],
                    "keyword": item.get("keyword"),
                    "keyword_color": item.get("keyword_color", "#ff7100"),
                    "keyword_border_color": item.get("keyword_border_color"),
                    "keyword_font_size": item.get("keyword_font_size", 15),
                    "font_size": item.get("font_size"),
                    "in_animation": item.get("in_animation"),
                    "out_animation": item.get("out_animation"),
                    "loop_animation": item.get("loop_animation"),
                    "in_animation_duration": item.get("in_animation_duration"),
                    "out_animation_duration": item.get("out_animation_duration"),
                    "loop_animation_duration": item.get("loop_animation_duration"),
                    "text_effect": item.get("text_effect")
                })
        return result
    except:
        return []


def hex_to_rgb(hex_str: str) -> tuple:
    """Convert hex color string to RGB tuple (0-1 range)."""
    if not hex_str: return (1.0, 1.0, 1.0)
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return (1.0, 1.0, 1.0)


def map_animation_name_to_enum(name: str, anim_type: str):
    """Map animation string name to corresponding enum."""
    category = {"in": TextIntro, "out": TextOutro, "loop": TextLoopAnim}.get(anim_type)
    if not category: return None
    for member in category:
        if member.value.name.lower() == name.lower():
            return member
    return None
