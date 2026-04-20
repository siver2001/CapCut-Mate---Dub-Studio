import json
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile
from src.pyJianYingDraft.keyframe import KeyframeProperty
from src.pyJianYingDraft.segment import VisualSegment
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
from src.utils.draft_lock_manager import DraftLockManager


def add_keyframes(
    draft_url: str,
    keyframes: str
) -> Tuple[str, int, List[str]]:
    """
    Business logic for adding keyframes to CapCut draft.

    Args:
        draft_url: Draft URL
        keyframes: JSON string containing list of keyframe objects.
    
    Returns:
        tuple: (draft_url, keyframes_added, affected_segments)
    """
    logger.info(f"add_keyframes started, draft_url: {draft_url}")

    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        logger.error(f"Invalid draft_url or draft not found in cache: {draft_url}")
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    keyframe_items = parse_keyframes_data(json_str=keyframes)
    if not keyframe_items:
        logger.info(f"No keyframe info provided for draft_id: {draft_id}")
        raise CustomException(CustomError.INVALID_KEYFRAME_INFO)

    script: ScriptFile = DRAFT_CACHE[draft_id]
    keyframes_added = 0
    affected_segments: List[str] = []

    for i, item in enumerate(keyframe_items):
        try:
            segment_id = item['segment_id']
            segment = find_segment_by_id(script, segment_id)
            
            if segment is None:
                logger.error(f"Segment not found: {segment_id}, skipping keyframe {i+1}")
                continue

            if not isinstance(segment, VisualSegment):
                logger.error(f"Segment {segment_id} is not a visual segment, skipping keyframe {i+1}")
                continue

            property_enum = KeyframeProperty(item['property'])
            time_offset = int(item['offset'])
            
            # Ensure time_offset is within segment duration
            time_offset = max(0, min(segment.duration, time_offset))
            
            segment.add_keyframe(property_enum, time_offset, item['value'])
            keyframes_added += 1
            if segment_id not in affected_segments:
                affected_segments.append(segment_id)
                
        except Exception as e:
            logger.error(f"Failed to add keyframe {i+1}: {str(e)}")

    script.save()
    logger.info(f"add_keyframes completed: {keyframes_added} keyframes added to {draft_id}")
    return draft_url, keyframes_added, affected_segments


async def add_keyframes_async(
    draft_url: str,
    keyframes: str,
    lock_timeout: float = 30.0
) -> Tuple[str, int, List[str]]:
    """Async version of add_keyframes with draft lock protection."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return add_keyframes(draft_url, keyframes)
    except asyncio.TimeoutError:
        logger.error(f"Timeout acquiring lock for draft {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)


def find_segment_by_id(script: ScriptFile, segment_id: str) -> Optional[VisualSegment]:
    """Find a visual segment by its ID."""
    for track in script.tracks.values():
        for segment in track.segments:
            if segment.segment_id == segment_id:
                return segment
    return None


def parse_keyframes_data(json_str: str) -> List[Dict[str, Any]]:
    """Parse and validate keyframe data JSON string."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e.msg}")
        raise CustomException(CustomError.INVALID_KEYFRAME_INFO, f"JSON parse error: {e.msg}")

    if not isinstance(data, list):
        raise CustomException(CustomError.INVALID_KEYFRAME_INFO, "keyframes must be a list")

    supported_properties = {
        "KFTypePositionX", "KFTypePositionY", "KFTypeScaleX",
        "KFTypeScaleY", "KFTypeRotation", "KFTypeAlpha", "UNIFORM_SCALE",
        "KFTypeSaturation", "KFTypeContrast", "KFTypeBrightness", "KFTypeVolume"
    }

    result = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue

        required = ["segment_id", "property", "offset", "value"]
        if all(field in item for field in required):
            if item["property"] in supported_properties:
                result.append({
                    "segment_id": str(item["segment_id"]),
                    "property": item["property"],
                    "offset": float(item["offset"]),
                    "value": float(item["value"])
                })
            else:
                logger.warning(f"Unsupported property: {item['property']} at index {i}")
        else:
            logger.warning(f"Missing required fields at index {i}")

    return result
