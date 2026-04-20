import json
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, TrackType, FilterSegment, Timerange
from src.pyJianYingDraft.metadata import FilterType
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
from src.utils.draft_lock_manager import DraftLockManager


def add_filters(
    draft_url: str,
    filter_infos: str
) -> Tuple[str, str, List[str], List[str]]:
    """
    Business logic for adding filters to CapCut draft (Synchronous version).
    """
    logger.info(f"add_filters started, draft_url: {draft_url}")
    
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    filter_items = parse_filters_data(filter_infos)
    if not filter_items:
        raise CustomException(CustomError.INVALID_FILTER_INFO)

    script: ScriptFile = DRAFT_CACHE[draft_id]
    track_name = f"filter_track_{helper.gen_unique_id()}"
    script.add_track(track_type=TrackType.filter, track_name=track_name)

    segment_ids = []
    filter_ids = []
    for item in filter_items:
        try:
            segment_id, filter_id = add_filter_to_draft(script, track_name, filter_item=item)
            segment_ids.append(segment_id)
            filter_ids.append(filter_id)
        except Exception as e:
            logger.error(f"Failed to add filter: {str(e)}")

    script.save()
    
    track_id = ""
    for track in script.tracks.values():
        if track.name == track_name:
            track_id = track.track_id
            break

    return draft_url, track_id, filter_ids, segment_ids


async def add_filters_async(
    draft_url: str,
    filter_infos: str,
    lock_timeout: float = 30.0
) -> Tuple[str, str, List[str], List[str]]:
    """Async version of add_filters with draft lock protection."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return add_filters(draft_url, filter_infos)
    except asyncio.TimeoutError:
        logger.error(f"Timeout acquiring lock for draft {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)


def add_filter_to_draft(
    script: ScriptFile,
    track_name: str,
    filter_item: dict
) -> Tuple[str, str]:
    """Add a single filter segment to a track."""
    filter_type = find_filter_type_by_name(filter_item['filter_title'])
    if not filter_type:
        raise CustomException(CustomError.FILTER_NOT_FOUND)

    timerange = Timerange(start=filter_item['start'], duration=filter_item['end'] - filter_item['start'])
    intensity = filter_item.get('intensity', 100.0)
    
    filter_segment = FilterSegment(
        meta=filter_type,
        target_timerange=timerange,
        intensity=intensity / 100.0
    )
    
    script.add_segment(filter_segment, track_name)
    return filter_segment.segment_id, filter_segment.material.global_id


def find_filter_type_by_name(filter_title: str) -> Optional[FilterType]:
    """Map filter title to FilterType enum."""
    for ft in FilterType:
        if ft.value.name.lower() == filter_title.lower():
            return ft
    return None


def parse_filters_data(json_str: str) -> List[Dict[str, Any]]:
    """Parse and validate filter metadata from JSON string."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, list): return []
        
        result = []
        for item in data:
            if all(k in item for k in ["filter_title", "start", "end"]):
                result.append({
                    "filter_title": str(item["filter_title"]),
                    "start": int(item["start"]),
                    "end": int(item["end"]),
                    "intensity": float(item.get("intensity", 100.0))
                })
        return result
    except:
        return []
