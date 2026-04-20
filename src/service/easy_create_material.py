import json
import os
from typing import Optional
from urllib.parse import urlparse
import asyncio
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, TrackType, trange, TextSegment, TextStyle, ClipSettings
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
import config
from src.utils.draft_lock_manager import DraftLockManager


def easy_create_material(
    draft_url: str,
    audio_url: str,
    text: Optional[str] = None,
    img_url: Optional[str] = None,
    video_url: Optional[str] = None,
    text_color: str = "#ffffff",
    font_size: int = 15,
    text_transform_y: int = 0
) -> str:
    """
    Shortcut for adding multiple material types (Audio, Video, Image, Text) to an existing draft.
    """
    logger.info(f"easy_create_material started for draft: {draft_url}")
    
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    if not audio_url or audio_url.lower() == "null":
        raise CustomException(CustomError.MATERIAL_CREATE_FAILED, detail="Audio URL is required")

    script: ScriptFile = DRAFT_CACHE[draft_id]

    try:
        # Mandatory Audio
        add_audio_material(script, draft_id, audio_url)

        # Optional Video
        if video_url and video_url.lower() != "null":
            add_video_material(script, draft_id, video_url)

        # Optional Image
        if img_url and img_url.lower() != "null":
            add_image_material(script, draft_id, img_url)

        # Optional Text
        if text and text.strip():
            add_text_material(script, text, text_color, font_size, text_transform_y)

        script.save()
        return draft_url
    except Exception as e:
        logger.error(f"Failed to create materials: {str(e)}")
        raise CustomException(CustomError.MATERIAL_CREATE_FAILED)


async def easy_create_material_async(
    draft_url: str,
    audio_url: str,
    text: Optional[str] = None,
    img_url: Optional[str] = None,
    video_url: Optional[str] = None,
    text_color: str = "#ffffff",
    font_size: int = 15,
    text_transform_y: int = 0,
    lock_timeout: float = 30.0
) -> str:
    """Async version of easy_create_material with draft lock protection."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return easy_create_material(
            draft_url, audio_url, text, img_url, video_url,
            text_color, font_size, text_transform_y
        )
    except asyncio.TimeoutError:
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)


def add_video_material(script: ScriptFile, draft_id: str, video_url: str) -> bool:
    from src.service.add_videos import parse_video_data, add_video_to_draft
    draft_video_dir = os.path.join(config.DRAFT_DIR, draft_id, "assets", "videos")
    os.makedirs(draft_video_dir, exist_ok=True)
    
    info = json.dumps([{"video_url": video_url, "width": 1920, "height": 1080, "start": 0, "end": 5000000}])
    items = parse_video_data(info)
    if not items: return False
    
    track_name = f"video_track_{helper.gen_unique_id()}"
    script.add_track(track_type=TrackType.video, track_name=track_name, relative_index=10)
    add_video_to_draft(script, track_name, draft_video_dir, items[0])
    return True


def add_image_material(script: ScriptFile, draft_id: str, img_url: str) -> bool:
    from src.service.add_images import parse_image_data, add_image_to_draft
    draft_image_dir = os.path.join(config.DRAFT_DIR, draft_id, "assets", "images")
    os.makedirs(draft_image_dir, exist_ok=True)
    
    info = json.dumps([{"image_url": img_url, "width": 1024, "height": 1024, "start": 0, "end": 3000000}])
    items = parse_image_data(info)
    if not items: return False
    
    track_name = f"image_track_{helper.gen_unique_id()}"
    script.add_track(track_type=TrackType.video, track_name=track_name, relative_index=10)
    add_image_to_draft(script, track_name, draft_image_dir, items[0])
    return True


def add_audio_material(script: ScriptFile, draft_id: str, audio_url: str) -> bool:
    from src.service.add_audios import parse_audio_data, add_audio_to_draft
    draft_audio_dir = os.path.join(config.DRAFT_DIR, draft_id, "assets", "audios")
    os.makedirs(draft_audio_dir, exist_ok=True)
    
    info = json.dumps([{"audio_url": audio_url, "start": 0, "end": 5000000, "volume": 1.0}])
    items = parse_audio_data(info)
    if not items: return False
    
    track_name = f"audio_track_{helper.gen_unique_id()}"
    script.add_track(track_type=TrackType.audio, track_name=track_name, relative_index=10)
    add_audio_to_draft(script, track_name, draft_audio_dir, items[0])
    return True


def add_text_material(script: ScriptFile, text: str, color: str, size: int, y_offset: int) -> bool:
    track_name = f"text_track_{helper.gen_unique_id()}"
    script.add_track(track_type=TrackType.text, track_name=track_name)
    
    rgb = hex_to_rgb(color)
    style = TextStyle(align=1, color=(rgb[0], rgb[1], rgb[2]), size=float(size))
    clip = ClipSettings(transform_y=y_offset / script.height)
    
    segment = TextSegment(text=text, timerange=trange(0, 5000000), style=style, clip_settings=clip)
    script.add_segment(segment, track_name)
    return True


def hex_to_rgb(hex_str: str) -> list:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6: hex_str = "ffffff"
    try:
        return [int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    except ValueError:
        return [1.0, 1.0, 1.0]
