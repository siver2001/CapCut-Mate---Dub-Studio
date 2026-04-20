import os
import json
import asyncio
import time
from typing import List, Dict, Any, Tuple, Optional
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, trange
import src.pyJianYingDraft as draft
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.schemas.add_images import SegmentInfo
from src.utils import helper
from src.utils.download import download
import config
from src.utils.draft_lock_manager import DraftLockManager
from src.pyJianYingDraft.metadata import IntroType, OutroType, GroupAnimationType, TransitionType


def add_images(
    draft_url: str,
    image_infos: str,
    alpha: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0
) -> Tuple[str, str, List[str], List[str], List[SegmentInfo]]:
    """
    Business logic for adding images to CapCut draft (Synchronous version).
    """
    return _add_images_internal(
        draft_url=draft_url,
        image_infos=image_infos,
        alpha=alpha,
        scale_x=scale_x,
        scale_y=scale_y,
        transform_x=transform_x,
        transform_y=transform_y,
        prepared_images=None,
    )


async def add_images_async(
    draft_url: str,
    image_infos: str,
    alpha: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0,
    lock_timeout: float = 30.0
) -> Tuple[str, str, List[str], List[str], List[SegmentInfo]]:
    """Async version of add_images with draft lock protection."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    prepared_images = await asyncio.to_thread(
        _prepare_images_local_files,
        draft_url,
        image_infos
    )

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return _add_images_internal(
            draft_url=draft_url,
            image_infos=image_infos,
            alpha=alpha,
            scale_x=scale_x,
            scale_y=scale_y,
            transform_x=transform_x,
            transform_y=transform_y,
            prepared_images=prepared_images
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout acquiring lock for draft {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)


def _prepare_images_local_files(draft_url: str, image_infos: str) -> List[Dict[str, Any]]:
    """Download image materials without modifying the script."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
    draft_image_dir = os.path.join(draft_dir, "assets", "images")
    os.makedirs(draft_image_dir, exist_ok=True)

    images = parse_image_data(image_infos)
    for image in images:
        image["local_image_path"] = download(url=image["image_url"], save_dir=draft_image_dir)
    
    return images


def _add_images_internal(
    draft_url: str,
    image_infos: str,
    alpha: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0,
    prepared_images: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, str, List[str], List[str], List[SegmentInfo]]:
    """Internal logic for adding images to a draft."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    if prepared_images is not None:
        images = prepared_images
    else:
        images = _prepare_images_local_files(draft_url, image_infos)

    script: ScriptFile = DRAFT_CACHE[draft_id]
    track_name = f"image_track_{helper.gen_unique_id()}"
    script.add_track(track_type=draft.TrackType.video, track_name=track_name, relative_index=10)

    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
    draft_image_dir = os.path.join(draft_dir, "assets", "images")

    segment_ids = []
    segment_infos = []
    for image in images:
        segment_id, segment_info = add_image_to_draft(
            script, track_name, draft_image_dir, image,
            alpha, scale_x, scale_y, transform_x, transform_y
        )
        segment_ids.append(segment_id)
        segment_infos.append(segment_info)

    script.save()
    
    track_id = ""
    for track in script.tracks.values():
        if track.name == track_name:
            track_id = track.track_id
            break

    image_ids = [v.material_id for v in script.materials.videos if v.material_type == "photo"]
    return draft_url, track_id, image_ids, segment_ids, segment_infos


def add_image_to_draft(
    script: ScriptFile,
    track_name: str,
    draft_image_dir: str,
    image: dict,
    alpha: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0
) -> Tuple[str, SegmentInfo]:
    """Add a single image segment to a specific track."""
    image_path = image.get("local_image_path")
    if not image_path:
        image_path = download(url=image["image_url"], save_dir=draft_image_dir)

    segment_duration = image['end'] - image['start']
    clip_settings = draft.ClipSettings(
        alpha=alpha, scale_x=scale_x, scale_y=scale_y,
        transform_x=transform_x / script.width,
        transform_y=transform_y / script.height
    )

    video_segment = draft.VideoSegment(
        material=image_path,
        target_timerange=trange(start=image['start'], duration=segment_duration),
        clip_settings=clip_settings
    )

    # Animations
    for anim_type in ["in", "out", "group"]:
        anim_name = image.get(f'{anim_type}_animation')
        if anim_name:
            anim_enum = map_video_animation_name_to_enum(anim_name, anim_type)
            if anim_enum:
                duration = image.get(f'{anim_type}_animation_duration')
                video_segment.add_animation(anim_enum, duration=int(duration) if duration else None)

    # Transition
    trans_name = image.get('transition')
    if trans_name:
        for attr_name in dir(TransitionType):
            attr = getattr(TransitionType, attr_name)
            if isinstance(attr, TransitionType) and attr.value.name == trans_name:
                video_segment.add_transition(attr, duration=int(image.get('transition_duration', 500000)))
                break

    script.add_segment(video_segment, track_name)
    return video_segment.segment_id, SegmentInfo(id=video_segment.segment_id, start=image['start'], end=image['end'])


def map_video_animation_name_to_enum(name: str, anim_type: str):
    """Map animation string name to metadata enum."""
    category = {"in": IntroType, "out": OutroType, "group": GroupAnimationType}.get(anim_type)
    if not category: return None
    for attr_name in dir(category):
        attr = getattr(category, attr_name)
        if isinstance(attr, category) and attr.value.title.lower() == name.lower():
            return attr
    return None


def parse_image_data(json_str: str) -> List[Dict[str, Any]]:
    """Parse and validate image metadata from JSON string."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, list): return []
        
        result = []
        for item in data:
            if all(k in item for k in ["image_url", "width", "height", "start", "end"]):
                result.append({
                    "image_url": item["image_url"],
                    "width": int(item["width"]),
                    "height": int(item["height"]),
                    "start": int(item["start"]),
                    "end": int(item["end"]),
                    "in_animation": item.get("in_animation"),
                    "out_animation": item.get("out_animation"),
                    "loop_animation": item.get("loop_animation"),
                    "in_animation_duration": item.get("in_animation_duration"),
                    "out_animation_duration": item.get("out_animation_duration"),
                    "loop_animation_duration": item.get("loop_animation_duration"),
                    "transition": item.get("transition"),
                    "transition_duration": int(item.get("transition_duration", 500000))
                })
        return result
    except:
        return []
