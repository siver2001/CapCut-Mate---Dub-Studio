import asyncio
from typing import Tuple
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, trange, StickerSegment, ClipSettings
import src.pyJianYingDraft as draft
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
from src.utils.draft_lock_manager import DraftLockManager

def add_sticker(
    draft_url: str,
    sticker_id: str,
    start: int,
    end: int,
    scale: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0
) -> Tuple[str, str, str, str, int]:
    """
    Add a sticker to a CapCut draft.
    """
    logger.info(f"add_sticker: {sticker_id} from {start} to {end}")
    
    if end <= start:
        raise CustomException(CustomError.INVALID_STICKER_INFO, "End must be after start")

    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    script: ScriptFile = DRAFT_CACHE[draft_id]
    duration = end - start
    track_name = f"sticker_track_{helper.gen_unique_id()}"

    try:
        script.add_track(track_type=draft.TrackType.sticker, track_name=track_name)
        
        clip_settings = ClipSettings(
            scale_x=scale, 
            scale_y=scale, 
            transform_x=transform_x / script.width, 
            transform_y=transform_y / script.height
        )

        sticker = StickerSegment(
            resource_id=sticker_id, 
            target_timerange=trange(start=start, duration=duration), 
            clip_settings=clip_settings
        )

        script.add_segment(sticker, track_name)
        script.save()

        track_id = ""
        for t in script.tracks.values():
            if t.name == track_name:
                track_id = t.track_id
                break

        return (draft_url, sticker_id, track_id, sticker.segment_id, duration)

    except Exception as e:
        logger.error(f"Failed to add sticker: {str(e)}")
        raise CustomException(CustomError.STICKER_ADD_FAILED)


async def add_sticker_async(
    draft_url: str,
    sticker_id: str,
    start: int,
    end: int,
    scale: float = 1.0,
    transform_x: int = 0,
    transform_y: int = 0,
    lock_timeout: float = 30.0
) -> Tuple[str, str, str, str, int]:
    """Async version with lock protection."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return add_sticker(draft_url, sticker_id, start, end, scale, transform_x, transform_y)
    except asyncio.TimeoutError:
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)