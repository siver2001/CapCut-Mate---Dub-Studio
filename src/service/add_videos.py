import asyncio
import os
import json
import time
from typing import List, Dict, Any, Tuple, Optional
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, trange
import src.pyJianYingDraft as draft
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
from src.utils.download import download
import config
from src.utils.draft_lock_manager import get_draft_lock_manager


def add_videos(
    draft_url: str,
    video_infos: str,
    scene_timelines: Optional[List[Dict[str, int]]] = None,
    alpha: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0
) -> Tuple[str, str, List[str], List[str]]:
    """
    Business logic for adding videos to CapCut draft (Synchronous version).
    """
    return _add_videos_internal(
        draft_url=draft_url,
        video_infos=video_infos,
        scene_timelines=scene_timelines,
        alpha=alpha,
        scale_x=scale_x,
        scale_y=scale_y,
        transform_x=transform_x,
        transform_y=transform_y,
        prepared_videos=None,
    )


async def add_videos_async(
    draft_url: str,
    video_infos: str,
    scene_timelines: Optional[List[Dict[str, int]]] = None,
    alpha: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0,
    lock_timeout: float = 30.0
) -> Tuple[str, str, List[str], List[str]]:
    """
    Add videos to CapCut draft (Async version with lock protection).
    """
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    logger.info(f"[flow:add_videos] prep_start, draft_id: {draft_id}")
    
    # Download and prepare files in a thread pool to avoid blocking the event loop
    prepared_videos = await asyncio.to_thread(
        _prepare_videos_local_files,
        draft_url,
        video_infos
    )
    
    lock_manager = get_draft_lock_manager()
    logger.info(f"[flow:add_videos] lock_wait_start, draft_id: {draft_id}, timeout: {lock_timeout}s")
    
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        logger.info(f"[flow:add_videos] lock_acquired, draft_id: {draft_id}")
        
        return _add_videos_internal(
            draft_url=draft_url,
            video_infos=video_infos,
            scene_timelines=scene_timelines,
            alpha=alpha,
            scale_x=scale_x,
            scale_y=scale_y,
            transform_x=transform_x,
            transform_y=transform_y,
            prepared_videos=prepared_videos
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout waiting for lock on draft_id: {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)
        logger.info(f"[flow:add_videos] lock_released, draft_id: {draft_id}")


def _prepare_videos_local_files(draft_url: str, video_infos: str) -> List[Dict[str, Any]]:
    """Download video materials to draft directory."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
    draft_video_dir = os.path.join(draft_dir, "assets", "videos")
    os.makedirs(draft_video_dir, exist_ok=True)

    videos = parse_video_data(json_str=video_infos)
    if not videos:
        raise CustomException(CustomError.INVALID_VIDEO_INFO)

    for video in videos:
        video["original_start"] = video["start"]
        video["original_end"] = video["end"]
        video["local_video_path"] = download(url=video["video_url"], save_dir=draft_video_dir)

    return videos


def _add_videos_internal(
    draft_url: str,
    video_infos: str,
    scene_timelines: Optional[List[Dict[str, int]]] = None,
    alpha: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0,
    prepared_videos: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, str, List[str], List[str]]:
    """Internal logic for adding videos to a draft."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
    draft_video_dir = os.path.join(draft_dir, "assets", "videos")
    os.makedirs(draft_video_dir, exist_ok=True)

    if prepared_videos is not None:
        videos = prepared_videos
    else:
        videos = parse_video_data(json_str=video_infos)
        if not videos:
            raise CustomException(CustomError.INVALID_VIDEO_INFO)
        for video in videos:
            video["original_start"] = video["start"]
            video["original_end"] = video["end"]

    script: ScriptFile = DRAFT_CACHE[draft_id]
    track_name = f"video_track_{helper.gen_unique_id()}"
    script.add_track(track_type=draft.TrackType.video, track_name=track_name, relative_index=10)

    segment_ids = []
    current_track_end = 0
    for i, video in enumerate(videos):
        scene_timeline = scene_timelines[i] if scene_timelines and i < len(scene_timelines) else None
        
        # Adjust for continuity
        if i > 0 and current_track_end > 0:
            original_duration = video['original_end'] - video['original_start']
            video['start'] = current_track_end
            video['end'] = video['start'] + original_duration

        segment_id, actual_duration = add_video_to_draft(
            script, track_name, 
            draft_video_dir=draft_video_dir, 
            video=video,
            scene_timeline=scene_timeline,
            alpha=alpha, scale_x=scale_x, scale_y=scale_y,
            transform_x=transform_x, transform_y=transform_y
        )
        segment_ids.append(segment_id)
        current_track_end = video['start'] + actual_duration

    script.save()
    
    track_id = ""
    for track in script.tracks.values():
        if track.name == track_name:
            track_id = track.track_id
            break

    video_ids = [v.material_id for v in script.materials.videos]
    return draft_url, track_id, video_ids, segment_ids


def add_video_to_draft(
    script: ScriptFile,
    track_name: str,
    draft_video_dir: str,
    video: dict,
    scene_timeline: Optional[Dict[str, int]] = None,
    alpha: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0
) -> Tuple[str, int]:
    """Add a single video segment to a specific track."""
    video_path = video.get("local_video_path")
    if not video_path:
        video_path = download(url=video["video_url"], save_dir=draft_video_dir)

    video_material = draft.VideoMaterial(video_path)
    display_duration = video['end'] - video['start']
    
    speed = 1.0
    actual_duration = display_duration
    if scene_timeline:
        scene_duration = scene_timeline['end'] - scene_timeline['start']
        if scene_duration > 0:
            speed = display_duration / scene_duration
            actual_duration = scene_duration

    clip_settings = draft.ClipSettings(
        alpha=alpha,
        scale_x=scale_x,
        scale_y=scale_y,
        transform_x=transform_x / script.width,
        transform_y=transform_y / script.height
    )

    video_segment = draft.VideoSegment(
        material=video_material,
        target_timerange=trange(start=video['start'], duration=display_duration),
        source_timerange=trange(start=0, duration=min(video_material.duration, display_duration)),
        speed=speed,
        volume=video.get('volume', 0.0),
        clip_settings=clip_settings
    )

    transition_name = video.get('transition')
    if transition_name:
        transition_type = draft.TransitionType.from_name(transition_name)
        if transition_type:
            video_segment.add_transition(transition_type, duration=video.get('transition_duration', 500000))

    script.add_segment(video_segment, track_name)
    return video_segment.segment_id, actual_duration


def parse_video_data(json_str: str) -> List[Dict[str, Any]]:
    """Parse video metadata from JSON string."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise CustomException(CustomError.INVALID_VIDEO_INFO, f"JSON parse error: {e.msg}")

    if not isinstance(data, list):
        raise CustomException(CustomError.INVALID_VIDEO_INFO, "video_infos must be a list")

    result = []
    for item in data:
        if all(k in item for k in ["video_url", "start", "end"]):
            duration = item.get("duration", item["end"] - item["start"])
            result.append({
                "video_url": item["video_url"],
                "width": item.get("width"),
                "height": item.get("height"),
                "start": item["start"],
                "end": item["end"],
                "duration": duration,
                "mask": item.get("mask"),
                "transition": item.get("transition"),
                "transition_duration": item.get("transition_duration", 500000),
                "volume": max(0.0, min(10.0, item.get("volume", 1.0)))
            })
    return result
